"""
Integration tests for janus-web against a live running instance.

Prerequisites:
  - janus-web running at JANUS_WEB_URL (default: http://localhost:8000)
  - janus-controller reachable from janus-web
  - At least one registered node and one available image
  - A local-login user with known credentials

Run with:
    pytest webapp/janus/integration_tests.py -v \
        -m integration \
        --tb=short \
        [--janus-url=http://localhost:8000] \
        [--janus-user=username] \
        [--janus-pass=password]

Or via environment variables:
    JANUS_WEB_URL=http://localhost:8000 \
    JANUS_TEST_USER=username \
    JANUS_TEST_PASS=password \
    pytest webapp/janus/integration_tests.py -v -m integration
"""

import os
import time

import httpx
import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
BASE_URL = os.getenv("JANUS_WEB_URL", "http://localhost:8000")
TEST_USER = os.getenv("JANUS_TEST_USER", "")
TEST_PASS = os.getenv("JANUS_TEST_PASS", "")

# Name prefix for any resources created during tests (makes cleanup easy)
TEST_PREFIX = "pytest-integ-"


# ─────────────────────────────────────────────────────────────────────────────
# pytest hooks / options
# ─────────────────────────────────────────────────────────────────────────────
def pytest_addoption(parser):
    parser.addoption("--janus-url", default=BASE_URL, help="Base URL of janus-web")
    parser.addoption("--janus-user", default=TEST_USER, help="Login username")
    parser.addoption("--janus-pass", default=TEST_PASS, help="Login password")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def base_url(request):
    return request.config.getoption("--janus-url", default=BASE_URL)


@pytest.fixture(scope="session")
def credentials(request):
    return {
        "username": request.config.getoption("--janus-user", default=TEST_USER),
        "password": request.config.getoption("--janus-pass", default=TEST_PASS),
    }


@pytest.fixture(scope="session")
def authed_client(base_url, credentials):
    """
    Session-scoped httpx.Client that is authenticated against the live
    janus-web instance.  Handles CSRF automatically.
    """
    client = httpx.Client(base_url=base_url, follow_redirects=True, timeout=30)

    # 1. Fetch the home page to get a CSRF cookie
    r = client.get("/")
    assert r.status_code == 200, f"Home page returned {r.status_code}"
    csrf = client.cookies.get("csrftoken")
    assert csrf, "No csrftoken cookie set by home page"

    # 2. Log in with local-login form
    r = client.post(
        "/authentication/login/",
        data={
            "username": credentials["username"],
            "password": credentials["password"],
            "csrfmiddlewaretoken": csrf,
        },
        headers={"Referer": base_url + "/"},
    )
    # login_view always redirects back to /
    assert r.status_code == 200, f"Login redirect chain ended with {r.status_code}"

    # 3. Verify we are actually logged in by hitting a protected endpoint
    r = client.get("/janus/api/sessions/")
    assert r.status_code == 200, (
        f"Authentication failed — /janus/api/sessions/ returned {r.status_code}. "
        "Check credentials."
    )

    yield client
    client.close()


@pytest.fixture(scope="session")
def anon_client(base_url):
    """Unauthenticated client — used to verify 401 enforcement."""
    client = httpx.Client(base_url=base_url, follow_redirects=False, timeout=10)
    yield client
    client.close()


@pytest.fixture(scope="session")
def first_node(authed_client):
    """Return the first available node dict from the live system."""
    r = authed_client.get("/janus/api/nodes/")
    assert r.status_code == 200
    nodes = r.json().get("nodes", [])
    assert nodes, "No nodes registered — cannot run session tests"
    return nodes[0]


@pytest.fixture(scope="session")
def first_image(authed_client):
    """Return the name of the first image that has a tag (image key present)."""
    r = authed_client.get("/janus/api/images/")
    assert r.status_code == 200
    images = r.json().get("images", [])
    assert images, "No images available — cannot run session tests"
    # Prefer images that already have a tag
    tagged = [img for img in images if img.get("image")]
    return tagged[0]["image"] if tagged else images[0]["name"] + ":latest"


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────
def _csrf(client: httpx.Client) -> str:
    """Return the current csrftoken from the client's cookie jar."""
    return client.cookies.get("csrftoken", "")


def _post_json(client: httpx.Client, url: str, payload: dict) -> httpx.Response:
    """POST JSON with CSRF header (required by Django for non-form POSTs)."""
    return client.post(
        url,
        json=payload,
        headers={"X-CSRFToken": _csrf(client), "Referer": str(client.base_url)},
    )


def _delete(client: httpx.Client, url: str) -> httpx.Response:
    return client.delete(
        url,
        headers={"X-CSRFToken": _csrf(client), "Referer": str(client.base_url)},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Mark all tests in this file as "integration"
# ─────────────────────────────────────────────────────────────────────────────
pytestmark = pytest.mark.integration


# ═════════════════════════════════════════════════════════════════════════════
# 1. Authentication enforcement
# ═════════════════════════════════════════════════════════════════════════════
class TestAuthEnforcement:
    """Unauthenticated requests must be rejected (401)."""

    PROTECTED_ENDPOINTS = [
        "/janus/api/sessions/",
        "/janus/api/nodes/",
        "/janus/api/images/",
        "/janus/api/profiles/host/",
        "/janus/api/node-types/",
        "/janus/api/profile-choices/",
    ]

    @pytest.mark.parametrize("endpoint", PROTECTED_ENDPOINTS)
    def test_unauthenticated_get_returns_401(self, anon_client, endpoint):
        r = anon_client.get(endpoint)
        assert r.status_code == 401, (
            f"Expected 401 for unauthenticated GET {endpoint}, got {r.status_code}"
        )

    def test_unauthenticated_create_session_returns_401_or_403(self, anon_client):
        # Django's CSRF middleware fires before the auth check for POST requests
        # without a valid CSRF token, so 403 is also an acceptable rejection.
        r = anon_client.post(
            "/janus/api/sessions/create/",
            json={"image": "alpine:latest"},
        )
        assert r.status_code in (401, 403), (
            f"Expected 401 or 403 for unauthenticated POST, got {r.status_code}"
        )

    def test_unauthenticated_add_node_returns_401_or_403(self, anon_client):
        r = anon_client.post(
            "/janus/api/nodes/add/",
            json={"name": "x", "url": "tcp://1.2.3.4:9001", "type": 3},
        )
        assert r.status_code in (401, 403), (
            f"Expected 401 or 403 for unauthenticated POST, got {r.status_code}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 2. Node API
# ═════════════════════════════════════════════════════════════════════════════
class TestNodeApi:
    def test_get_nodes_returns_200_with_nodes_key(self, authed_client):
        r = authed_client.get("/janus/api/nodes/")
        assert r.status_code == 200
        data = r.json()
        assert "nodes" in data
        assert isinstance(data["nodes"], list)

    def test_nodes_list_is_non_empty(self, authed_client):
        r = authed_client.get("/janus/api/nodes/")
        nodes = r.json()["nodes"]
        assert len(nodes) > 0, "Expected at least one registered node"

    def test_node_has_required_fields(self, authed_client, first_node):
        for field in ("id", "name", "url", "status"):
            assert field in first_node, f"Node missing field: {field}"

    def test_node_status_is_active(self, authed_client, first_node):
        # status == 1 means active/connected
        assert first_node["status"] == 1, (
            f"Node '{first_node['name']}' is not active (status={first_node['status']})"
        )

    def test_get_nodes_with_refresh(self, authed_client):
        r = authed_client.get("/janus/api/nodes/?refresh=true")
        assert r.status_code == 200
        assert "nodes" in r.json()

    def test_node_types_returns_all_types(self, authed_client):
        r = authed_client.get("/janus/api/node-types/")
        assert r.status_code == 200
        data = r.json()
        # Keys are serialised as strings
        for key in ("1", "2", "3", "4", "100"):
            assert key in data, f"Missing node type key: {key}"

    def test_node_type_values_are_strings(self, authed_client):
        r = authed_client.get("/janus/api/node-types/")
        for k, v in r.json().items():
            assert isinstance(v, str), f"Node type {k} value is not a string: {v!r}"


# ═════════════════════════════════════════════════════════════════════════════
# 3. Image API
# ═════════════════════════════════════════════════════════════════════════════
class TestImageApi:
    def test_get_images_returns_200(self, authed_client):
        r = authed_client.get("/janus/api/images/")
        assert r.status_code == 200

    def test_images_key_is_list(self, authed_client):
        r = authed_client.get("/janus/api/images/")
        assert isinstance(r.json().get("images"), list)

    def test_images_list_is_non_empty(self, authed_client):
        r = authed_client.get("/janus/api/images/")
        assert len(r.json()["images"]) > 0

    def test_each_image_has_name_field(self, authed_client):
        r = authed_client.get("/janus/api/images/")
        for img in r.json()["images"]:
            assert "name" in img, f"Image entry missing 'name': {img}"


# ═════════════════════════════════════════════════════════════════════════════
# 4. Profile API
# ═════════════════════════════════════════════════════════════════════════════
class TestProfileApi:
    def test_get_host_profiles_returns_200(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/")
        assert r.status_code == 200
        assert "profiles" in r.json()

    def test_host_profiles_list_is_non_empty(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/")
        assert len(r.json()["profiles"]) > 0

    def test_each_host_profile_has_required_fields(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/")
        for p in r.json()["profiles"]:
            for field in ("name", "settings", "is_system"):
                assert field in p, f"Profile missing field '{field}': {p}"

    def test_get_network_profiles_returns_200(self, authed_client):
        r = authed_client.get("/janus/api/profiles/network/")
        assert r.status_code == 200
        assert "profiles" in r.json()

    def test_get_volume_profiles_returns_200(self, authed_client):
        r = authed_client.get("/janus/api/profiles/volume/")
        assert r.status_code == 200
        assert "profiles" in r.json()

    def test_get_qos_profiles_returns_200(self, authed_client):
        r = authed_client.get("/janus/api/profiles/qos/")
        assert r.status_code == 200
        assert "profiles" in r.json()

    def test_profile_choices_returns_qos_networks_volumes(self, authed_client):
        r = authed_client.get("/janus/api/profile-choices/")
        assert r.status_code == 200
        data = r.json()
        for key in ("qos", "networks", "volumes"):
            assert key in data, f"profile-choices missing key: {key}"
            assert isinstance(data[key], list)

    def test_host_profiles_with_refresh(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/?refresh=true")
        assert r.status_code == 200
        assert "profiles" in r.json()

    def test_default_profile_exists(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/")
        names = [p["name"] for p in r.json()["profiles"]]
        assert "default" in names, f"'default' profile not found; profiles: {names}"

    def test_default_profile_is_system(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/")
        default = next(p for p in r.json()["profiles"] if p["name"] == "default")
        assert default["is_system"] is True

    def test_default_profile_settings_have_cpu_and_memory(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/")
        default = next(p for p in r.json()["profiles"] if p["name"] == "default")
        settings = default["settings"]
        assert "cpu" in settings
        assert "memory" in settings
        assert settings["cpu"] > 0
        assert settings["memory"] > 0


# ═════════════════════════════════════════════════════════════════════════════
# 5. Session lifecycle
# ═════════════════════════════════════════════════════════════════════════════
class TestSessionLifecycle:
    """
    Full create → update → start → stop → delete lifecycle against the live
    controller.  Each test depends on the previous one via class-level state.
    """

    # Class-level state shared across tests in this class
    _session_id = None

    def test_01_get_sessions_returns_list(self, authed_client):
        r = authed_client.get("/janus/api/sessions/")
        assert r.status_code == 200
        data = r.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)

    def test_02_create_session(self, authed_client, first_node, first_image):
        # The controller's SessionRequest (models_api.py) requires:
        #   instances: List[Union[dict, str]]  — list of node names or constraint dicts
        #   image: str
        #   profile: str
        # janus-web passes the payload dict directly to the controller via httpx.
        payload = {
            "name": TEST_PREFIX + "session",
            "instances": [first_node["name"]],
            "image": first_image,
            "profile": "default",
        }
        r = _post_json(authed_client, "/janus/api/sessions/create/", payload)
        assert r.status_code == 200, f"Create session failed: {r.text}"
        data = r.json()
        assert data.get("status") is True, f"Create session status=False: {data}"
        result = data.get("result", {})
        assert result, "Create session returned empty result"
        # result is a dict keyed by session_id
        session_id = int(list(result.keys())[0])
        TestSessionLifecycle._session_id = session_id

    def test_03_session_appears_in_list(self, authed_client):
        assert TestSessionLifecycle._session_id is not None, "No session created yet"
        r = authed_client.get("/janus/api/sessions/")
        sessions = r.json()["sessions"]
        ids = [s.get("id") for s in sessions]
        assert TestSessionLifecycle._session_id in ids, (
            f"Session {TestSessionLifecycle._session_id} not found in list: {ids}"
        )

    def test_04_update_session_name(self, authed_client, first_node, first_image):
        sid = TestSessionLifecycle._session_id
        assert sid is not None
        # The controller's update endpoint validates the full SessionRequest,
        # so we must include all required fields (instances, image, profile).
        payload = {
            "name": TEST_PREFIX + "session-renamed",
            "instances": [first_node["name"]],
            "image": first_image,
            "profile": "default",
        }
        r = _post_json(authed_client, f"/janus/api/sessions/{sid}/update/", payload)
        assert r.status_code == 200, f"Update session failed: {r.text}"
        data = r.json()
        assert data.get("status") is True, f"Update returned status=False: {data}"

    def test_05_start_session(self, authed_client):
        sid = TestSessionLifecycle._session_id
        assert sid is not None
        r = authed_client.get(f"/janus/api/sessions/{sid}/start/")
        assert r.status_code == 200, f"Start session failed: {r.text}"
        data = r.json()
        assert data.get("status") is True, f"Start returned status=False: {data}"

    def test_06_session_is_running_after_start(self, authed_client):
        sid = TestSessionLifecycle._session_id
        assert sid is not None
        # Give the controller a moment to spin up the container
        time.sleep(2)
        r = authed_client.get("/janus/api/sessions/")
        sessions = r.json()["sessions"]
        session = next((s for s in sessions if s.get("id") == sid), None)
        assert session is not None, f"Session {sid} not found after start"
        # The controller serialises state as a string: "STARTED", "STOPPED", etc.
        state = session.get("state")
        assert state in ("STARTED", "RUNNING", "STARTING"), (
            f"Session {sid} not in running state after start: state={state!r}"
        )

    def test_07_get_session_logs(self, authed_client, first_node):
        sid = TestSessionLifecycle._session_id
        assert sid is not None
        r = authed_client.get(f"/janus/api/sessions/{sid}/logs/{first_node['name']}/")
        assert r.status_code == 200, f"Get logs failed: {r.text}"
        data = r.json()
        # Should return a log dict (may be empty if container just started)
        assert isinstance(data, dict)

    def test_08_stop_session(self, authed_client):
        sid = TestSessionLifecycle._session_id
        assert sid is not None
        r = authed_client.get(f"/janus/api/sessions/{sid}/stop/")
        assert r.status_code == 200, f"Stop session failed: {r.text}"
        data = r.json()
        assert data.get("status") is True, f"Stop returned status=False: {data}"

    def test_08b_session_state_is_stopped(self, authed_client):
        """After stop, re-fetch the session list and verify state is STOPPED."""
        sid = TestSessionLifecycle._session_id
        assert sid is not None
        # Allow the controller a moment to transition state
        time.sleep(3)
        r = authed_client.get("/janus/api/sessions/")
        assert r.status_code == 200
        sessions = r.json()["sessions"]
        session = next((s for s in sessions if s.get("id") == sid), None)
        assert session is not None, f"Session {sid} not found in list after stop"
        state = session.get("state")
        assert state in ("STOPPED", "STOPPING", "CREATED"), (
            f"Session {sid} not in a stopped state after stop: state={state!r}"
        )

    def test_09_delete_session(self, authed_client):
        sid = TestSessionLifecycle._session_id
        assert sid is not None
        r = authed_client.get(f"/janus/api/sessions/{sid}/delete/")
        assert r.status_code == 200, f"Delete session failed: {r.text}"
        data = r.json()
        assert data.get("status") is True, f"Delete returned status=False: {data}"

    def test_10_session_gone_after_delete(self, authed_client):
        sid = TestSessionLifecycle._session_id
        assert sid is not None
        r = authed_client.get("/janus/api/sessions/")
        sessions = r.json()["sessions"]
        ids = [s.get("id") for s in sessions]
        assert sid not in ids, f"Session {sid} still present after delete"


# ═════════════════════════════════════════════════════════════════════════════
# 6. Profile CRUD lifecycle (non-system profiles only)
# ═════════════════════════════════════════════════════════════════════════════
class TestProfileCrudLifecycle:
    """
    Create → update → delete a host profile.
    Requires the test user to be staff (admin).
    """

    _profile_name = TEST_PREFIX + "profile"

    def test_01_create_host_profile(self, authed_client):
        payload = {
            "name": self._profile_name,
            "settings": {
                "cpu": 2.0,
                "memory": 4294967296,  # 4 GB
                "mgmt_net": "bridge",
                "affinity": "network",
                "privileged": False,
                "pull_image": False,
                "systemd": False,
                "ctrl_ports": [[30000, 30200]],
                "environment": [],
                "features": [],
                "post_starts": [],
                "volumes": [],
                "tools": {},
            },
        }
        r = _post_json(authed_client, "/janus/api/profiles/host/create/", payload)
        assert r.status_code == 200, f"Create profile failed ({r.status_code}): {r.text}"
        data = r.json()
        assert data.get("status") is True, f"Create profile status=False: {data}"

    def test_02_profile_appears_in_list(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/")
        names = [p["name"] for p in r.json()["profiles"]]
        assert self._profile_name in names, (
            f"Profile '{self._profile_name}' not found after create; profiles: {names}"
        )

    def test_03_update_host_profile(self, authed_client):
        payload = {
            "name": self._profile_name,
            "settings": {
                "cpu": 4.0,
                "memory": 8589934592,  # 8 GB
                "mgmt_net": "bridge",
                "affinity": "network",
                "privileged": False,
                "pull_image": False,
                "systemd": False,
                "ctrl_ports": [[30000, 30200]],
                "environment": [],
                "features": [],
                "post_starts": [],
                "volumes": [],
                "tools": {},
            },
        }
        r = _post_json(authed_client, "/janus/api/profiles/host/update/", payload)
        assert r.status_code == 200, f"Update profile failed ({r.status_code}): {r.text}"
        data = r.json()
        assert data.get("status") is True, f"Update profile status=False: {data}"

    def test_04_updated_profile_has_new_cpu(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/")
        profile = next(
            (p for p in r.json()["profiles"] if p["name"] == self._profile_name), None
        )
        assert profile is not None
        assert profile["settings"]["cpu"] == 4.0, (
            f"Expected cpu=4.0 after update, got {profile['settings']['cpu']}"
        )

    def test_05_delete_host_profile(self, authed_client):
        r = _delete(authed_client, f"/janus/api/profiles/host/delete/{self._profile_name}/")
        assert r.status_code == 200, f"Delete profile failed ({r.status_code}): {r.text}"
        data = r.json()
        assert data.get("status") is True, f"Delete profile status=False: {data}"

    def test_06_profile_gone_after_delete(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/")
        names = [p["name"] for p in r.json()["profiles"]]
        assert self._profile_name not in names, (
            f"Profile '{self._profile_name}' still present after delete"
        )

    def test_07_cannot_delete_system_profile(self, authed_client):
        """Deleting the 'default' system profile must fail."""
        r = _delete(authed_client, "/janus/api/profiles/host/delete/default/")
        # Either 400 (service rejects it) or 200 with status=False
        if r.status_code == 200:
            assert r.json().get("status") is False, (
                "Deleting system profile 'default' should return status=False"
            )
        else:
            assert r.status_code in (400, 403), (
                f"Unexpected status code when deleting system profile: {r.status_code}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 7. HTTP method enforcement
# ═════════════════════════════════════════════════════════════════════════════
class TestMethodEnforcement:
    """POST-only endpoints must reject GET (405)."""

    def test_create_session_rejects_get(self, authed_client):
        r = authed_client.get("/janus/api/sessions/create/")
        assert r.status_code == 405

    def test_update_session_rejects_get(self, authed_client):
        r = authed_client.get("/janus/api/sessions/9999/update/")
        assert r.status_code == 405

    def test_add_node_rejects_get(self, authed_client):
        r = authed_client.get("/janus/api/nodes/add/")
        assert r.status_code == 405

    def test_create_profile_rejects_get(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/create/")
        assert r.status_code == 405

    def test_update_profile_rejects_get(self, authed_client):
        r = authed_client.get("/janus/api/profiles/host/update/")
        assert r.status_code == 405


# ═════════════════════════════════════════════════════════════════════════════
# 8. Bad-input handling
# ═════════════════════════════════════════════════════════════════════════════
class TestBadInputHandling:
    def test_create_session_with_invalid_json_returns_400(self, authed_client):
        r = authed_client.post(
            "/janus/api/sessions/create/",
            content=b"not-json",
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": _csrf(authed_client),
                "Referer": str(authed_client.base_url),
            },
        )
        assert r.status_code == 400
        assert "error" in r.json() or "Invalid JSON" in r.text

    def test_update_session_with_invalid_json_returns_400(self, authed_client):
        r = authed_client.post(
            "/janus/api/sessions/9999/update/",
            content=b"not-json",
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": _csrf(authed_client),
                "Referer": str(authed_client.base_url),
            },
        )
        assert r.status_code == 400

    def test_add_node_with_invalid_json_returns_400(self, authed_client):
        r = authed_client.post(
            "/janus/api/nodes/add/",
            content=b"not-json",
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": _csrf(authed_client),
                "Referer": str(authed_client.base_url),
            },
        )
        assert r.status_code == 400

    def test_create_profile_with_invalid_json_returns_400(self, authed_client):
        r = authed_client.post(
            "/janus/api/profiles/host/create/",
            content=b"not-json",
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": _csrf(authed_client),
                "Referer": str(authed_client.base_url),
            },
        )
        assert r.status_code == 400