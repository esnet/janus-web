"""
Comprehensive tests for janus-web Django application.

Covers:
  - janus.utils.convert_size()
  - janus.views.validate_environment_vars()
  - All JSON API views (with mocked services)
"""
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from janus.utils import convert_size
from janus.views import validate_environment_vars


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _make_user(username="testuser", password="testpass", is_staff=False):
    """Create and return a Django User for testing."""
    user = User.objects.create_user(username=username, password=password)
    user.is_staff = is_staff
    user.save()
    return user


# ─────────────────────────────────────────────────────────────────────────────
# 1. convert_size
# ─────────────────────────────────────────────────────────────────────────────
class TestConvertSize(TestCase):
    """Tests for janus.utils.convert_size()."""

    def test_none_returns_default(self):
        self.assertEqual(convert_size(None), "default")

    def test_zero_returns_default(self):
        # 0 is falsy → caught by `if not size_bytes` before the == 0 check
        self.assertEqual(convert_size(0), "default")

    def test_empty_string_returns_default(self):
        self.assertEqual(convert_size(""), "default")

    def test_one_byte(self):
        self.assertEqual(convert_size(1), "1 B")

    def test_512_bytes(self):
        # floor(log(512, 1024)) = 0 → B; 512/1 = 512
        self.assertEqual(convert_size(512), "512 B")

    def test_1_kilobyte(self):
        self.assertEqual(convert_size(1024), "1 KB")

    def test_1500_bytes_rounds_to_1_kb(self):
        # floor(log(1500, 1024)) = 1 → KB; 1500/1024 ≈ 1.46 → round = 1
        self.assertEqual(convert_size(1500), "1 KB")

    def test_1_megabyte(self):
        self.assertEqual(convert_size(1024 ** 2), "1 MB")

    def test_1_gigabyte(self):
        self.assertEqual(convert_size(1024 ** 3), "1 GB")

    def test_1_terabyte(self):
        self.assertEqual(convert_size(1024 ** 4), "1 TB")

    def test_1_petabyte(self):
        self.assertEqual(convert_size(1024 ** 5), "1 PB")


# ─────────────────────────────────────────────────────────────────────────────
# 2. validate_environment_vars
# ─────────────────────────────────────────────────────────────────────────────
class TestValidateEnvironmentVars(TestCase):
    """Tests for janus.views.validate_environment_vars()."""

    def test_empty_string(self):
        valid, errors = validate_environment_vars("")
        self.assertEqual(valid, [])
        self.assertEqual(errors, [])

    def test_single_valid_var(self):
        valid, errors = validate_environment_vars("MY_VAR=hello")
        self.assertEqual(valid, ["MY_VAR=hello"])
        self.assertEqual(errors, [])

    def test_multiple_valid_vars(self):
        valid, errors = validate_environment_vars("FOO=bar\nBAZ=qux")
        self.assertEqual(valid, ["FOO=bar", "BAZ=qux"])
        self.assertEqual(errors, [])

    def test_blank_lines_are_skipped(self):
        valid, errors = validate_environment_vars("FOO=bar\n\nBAZ=qux\n")
        self.assertEqual(valid, ["FOO=bar", "BAZ=qux"])
        self.assertEqual(errors, [])

    def test_value_whitespace_is_stripped(self):
        valid, errors = validate_environment_vars("KEY=  hello world  ")
        self.assertEqual(valid, ["KEY=hello world"])
        self.assertEqual(errors, [])

    def test_missing_equals_sign(self):
        valid, errors = validate_environment_vars("NOEQUALS")
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Missing '='", errors[0])
        self.assertIn("Line 1", errors[0])

    def test_multiple_equals_signs(self):
        valid, errors = validate_environment_vars("KEY=val=extra")
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Multiple '='", errors[0])

    def test_empty_key(self):
        valid, errors = validate_environment_vars("=value")
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Empty environment variable name", errors[0])

    def test_key_starts_with_digit(self):
        valid, errors = validate_environment_vars("1INVALID=value")
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid environment variable name format", errors[0])

    def test_key_with_hyphen(self):
        valid, errors = validate_environment_vars("MY-VAR=value")
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid environment variable name format", errors[0])

    def test_key_with_space(self):
        valid, errors = validate_environment_vars("MY VAR=value")
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("Invalid environment variable name format", errors[0])

    def test_lowercase_key_is_valid(self):
        # re.I flag makes it case-insensitive
        valid, errors = validate_environment_vars("my_var=hello")
        self.assertEqual(valid, ["my_var=hello"])
        self.assertEqual(errors, [])

    def test_underscore_start_is_valid(self):
        valid, errors = validate_environment_vars("_PRIVATE=secret")
        self.assertEqual(valid, ["_PRIVATE=secret"])
        self.assertEqual(errors, [])

    def test_error_includes_line_number(self):
        valid, errors = validate_environment_vars("GOOD=ok\nBAD KEY=fail")
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("Line 2", errors[0])

    def test_mixed_valid_and_invalid(self):
        env_str = "GOOD=value\nBAD KEY=value\nALSOGOOD=123"
        valid, errors = validate_environment_vars(env_str)
        self.assertEqual(len(valid), 2)
        self.assertEqual(len(errors), 1)

    def test_multiple_errors(self):
        env_str = "NOEQUALS\n=empty_key\n1BADSTART=val"
        valid, errors = validate_environment_vars(env_str)
        self.assertEqual(valid, [])
        self.assertEqual(len(errors), 3)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Session API views
# ─────────────────────────────────────────────────────────────────────────────
class TestGetSessionsApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(reverse("janus:get_sessions_api"))
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

    def test_returns_sessions_on_success(self):
        sessions = [{"id": 1, "name": "test-session"}]
        with patch("janus.views.services.get_session_info", return_value=(True, sessions)):
            response = self.client.get(reverse("janus:get_sessions_api"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("sessions", data)
        self.assertEqual(data["sessions"], sessions)

    def test_service_failure_returns_500(self):
        with patch("janus.views.services.get_session_info", return_value=(False, "Connection error")):
            response = self.client.get(reverse("janus:get_sessions_api"))
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.json())

    def test_empty_sessions_list(self):
        with patch("janus.views.services.get_session_info", return_value=(True, [])):
            response = self.client.get(reverse("janus:get_sessions_api"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sessions"], [])


class TestCreateSessionApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:create_session_api")

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_get_method_returns_405(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_invalid_json_returns_400(self):
        response = self.client.post(self.url, data="not-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid JSON", response.json()["error"])

    def test_valid_request_calls_service(self):
        payload = {"image": "myimage:latest", "node": "node1"}
        with patch("janus.views.services.create_session", return_value=(True, {"1": {"id": 1}})) as mock_svc:
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])
        mock_svc.assert_called_once()

    def test_image_without_tag_gets_latest_appended(self):
        payload = {"image": "myimage"}
        with patch("janus.views.services.create_session", return_value=(True, {})) as mock_svc:
            self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        # The data dict passed as first positional arg should have image with :latest
        call_data = mock_svc.call_args[0][0]
        self.assertEqual(call_data["image"], "myimage:latest")

    def test_image_with_tag_is_unchanged(self):
        payload = {"image": "myimage:v1.2"}
        with patch("janus.views.services.create_session", return_value=(True, {})) as mock_svc:
            self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        call_data = mock_svc.call_args[0][0]
        self.assertEqual(call_data["image"], "myimage:v1.2")

    def test_service_failure_returns_400(self):
        payload = {"image": "myimage:latest"}
        with patch("janus.views.services.create_session", return_value=(False, "Error creating session")):
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["status"])

    def test_no_image_key_in_payload(self):
        payload = {"node": "node1"}
        with patch("janus.views.services.create_session", return_value=(True, {})) as mock_svc:
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        call_data = mock_svc.call_args[0][0]
        self.assertNotIn("image", call_data)


class TestUpdateSessionApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:update_session_api", kwargs={"session_id": 42})

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_get_method_returns_405(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_invalid_json_returns_400(self):
        response = self.client.post(self.url, data="bad-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_valid_update(self):
        payload = {"name": "new-name"}
        with patch("janus.views.services.update_session", return_value=(True, {"id": 42})):
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_apply_param_true_passed_to_service(self):
        payload = {"name": "new-name"}
        with patch("janus.views.services.update_session", return_value=(True, {})) as mock_svc:
            self.client.post(
                self.url + "?apply=true",
                data=json.dumps(payload),
                content_type="application/json",
            )
        # apply=True is the 5th positional arg (index 4)
        call_args = mock_svc.call_args[0]
        self.assertTrue(call_args[4])

    def test_apply_param_false_by_default(self):
        payload = {"name": "new-name"}
        with patch("janus.views.services.update_session", return_value=(True, {})) as mock_svc:
            self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        call_args = mock_svc.call_args[0]
        self.assertFalse(call_args[4])

    def test_image_without_tag_gets_latest(self):
        payload = {"image": "myimage"}
        with patch("janus.views.services.update_session", return_value=(True, {})) as mock_svc:
            self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        call_data = mock_svc.call_args[0][1]
        self.assertEqual(call_data["image"], "myimage:latest")

    def test_service_failure_returns_400(self):
        payload = {"name": "new-name"}
        with patch("janus.views.services.update_session", return_value=(False, "Error")):
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)


class TestApplySessionChangesApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:apply_session_changes_api", kwargs={"session_id": 42})

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_apply_calls_service_and_returns_200(self):
        with patch("janus.views.services.apply_session_changes", return_value=(True, {"id": 42})):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_service_failure_returns_400(self):
        with patch("janus.views.services.apply_session_changes", return_value=(False, "Error")):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["status"])


class TestStartSessionApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:start_session_api", kwargs={"session_id": 1})

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_start_session_success(self):
        with patch("janus.views.services.start_session", return_value=(True, {"id": 1})):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_start_session_failure(self):
        with patch("janus.views.services.start_session", return_value=(False, "Error")):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["status"])


class TestStopSessionApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:stop_session_api", kwargs={"session_id": 1})

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_stop_session_success(self):
        with patch("janus.views.services.stop_session", return_value=(True, {"id": 1})):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_stop_session_failure(self):
        with patch("janus.views.services.stop_session", return_value=(False, "Error")):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["status"])


class TestDeleteSessionApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:delete_session_api", kwargs={"session_id": 1})

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_delete_session_success(self):
        with patch("janus.views.services.delete_session", return_value=(True, {})):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_delete_session_failure(self):
        with patch("janus.views.services.delete_session", return_value=(False, "Error")):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["status"])


# ─────────────────────────────────────────────────────────────────────────────
# 4. Node API views
# ─────────────────────────────────────────────────────────────────────────────
class TestGetNodesApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:get_nodes_api")

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_returns_nodes_on_success(self):
        nodes = [{"name": "node1", "url": "http://node1"}]
        with patch("janus.views.services.get_nodes", return_value=(True, nodes)):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["nodes"], nodes)

    def test_service_failure_returns_500(self):
        with patch("janus.views.services.get_nodes", return_value=(False, [])):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)

    def test_refresh_param_true_passed_to_service(self):
        with patch("janus.views.services.get_nodes", return_value=(True, [])) as mock_svc:
            self.client.get(self.url + "?refresh=true")
        call_kwargs = mock_svc.call_args[1]
        self.assertTrue(call_kwargs.get("refresh"))

    def test_no_refresh_param_defaults_false(self):
        with patch("janus.views.services.get_nodes", return_value=(True, [])) as mock_svc:
            self.client.get(self.url)
        call_kwargs = mock_svc.call_args[1]
        self.assertFalse(call_kwargs.get("refresh"))


class TestAddNodeApi(TestCase):
    def setUp(self):
        self.staff_user = _make_user(username="admin", is_staff=True)
        self.regular_user = _make_user(username="regular")
        self.url = reverse("janus:add_node_api")

    def test_unauthenticated_returns_401(self):
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_non_staff_returns_401(self):
        self.client.force_login(self.regular_user)
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_get_method_returns_405(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(self.url, data="bad-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_staff_can_add_node(self):
        self.client.force_login(self.staff_user)
        payload = {"name": "newnode", "url": "http://newnode:9000", "type": 1}
        with patch("janus.views.services.add_node", return_value=(True, {"name": "newnode"})):
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_service_failure_returns_400(self):
        self.client.force_login(self.staff_user)
        payload = {"name": "newnode"}
        with patch("janus.views.services.add_node", return_value=(False, "Error")):
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)


class TestRemoveNodeApi(TestCase):
    def setUp(self):
        self.staff_user = _make_user(username="admin", is_staff=True)
        self.regular_user = _make_user(username="regular")
        self.url = reverse("janus:remove_node_api", kwargs={"nname": "mynode"})

    def test_unauthenticated_returns_401(self):
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 401)

    def test_non_staff_returns_401(self):
        self.client.force_login(self.regular_user)
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 401)

    def test_staff_can_remove_node(self):
        self.client.force_login(self.staff_user)
        with patch("janus.views.services.remove_node", return_value=(True, {})):
            response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_service_failure_returns_400(self):
        self.client.force_login(self.staff_user)
        with patch("janus.views.services.remove_node", return_value=(False, "Error")):
            response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 400)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Image API views
# ─────────────────────────────────────────────────────────────────────────────
class TestGetImagesApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:get_images_api")

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_returns_images_on_success(self):
        images = [{"name": "ubuntu:22.04"}, {"name": "alpine:latest"}]
        with patch("janus.views.services.get_images", return_value=(True, images)):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["images"], images)

    def test_service_failure_returns_500(self):
        with patch("janus.views.services.get_images", return_value=(False, [])):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Profile API views
# ─────────────────────────────────────────────────────────────────────────────
class TestGetProfilesApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(reverse("janus:get_profiles_api", kwargs={"resource": "host"}))
        self.assertEqual(response.status_code, 401)

    def test_returns_profiles_for_host(self):
        profiles = [{"name": "default"}, {"name": "custom"}]
        with patch("janus.views.services.get_profiles", return_value=(True, profiles)):
            response = self.client.get(reverse("janus:get_profiles_api", kwargs={"resource": "host"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profiles"], profiles)

    def test_returns_profiles_for_network(self):
        profiles = [{"name": "mynet"}]
        with patch("janus.views.services.get_profiles", return_value=(True, profiles)):
            response = self.client.get(reverse("janus:get_profiles_api", kwargs={"resource": "network"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["profiles"], profiles)

    def test_service_failure_returns_500(self):
        with patch("janus.views.services.get_profiles", return_value=(False, [])):
            response = self.client.get(reverse("janus:get_profiles_api", kwargs={"resource": "host"}))
        self.assertEqual(response.status_code, 500)

    def test_refresh_param_passed_to_service(self):
        with patch("janus.views.services.get_profiles", return_value=(True, [])) as mock_svc:
            self.client.get(
                reverse("janus:get_profiles_api", kwargs={"resource": "host"}) + "?refresh=true"
            )
        call_kwargs = mock_svc.call_args[1]
        self.assertTrue(call_kwargs.get("refresh"))


class TestGetNodeTypesApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:get_node_types_api")

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_returns_all_node_type_keys(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # JSON serialises integer dict keys as strings
        self.assertIn("1", data)
        self.assertIn("2", data)
        self.assertIn("3", data)
        self.assertIn("4", data)
        self.assertIn("100", data)

    def test_node_type_values_are_descriptive(self):
        response = self.client.get(self.url)
        data = response.json()
        self.assertIn("Portainer Agent", data["1"])
        self.assertIn("Kubernetes", data["2"])
        self.assertIn("Docker", data["3"])
        self.assertIn("Slurm", data["4"])
        self.assertIn("Edge", data["100"])


class TestGetProfileChoicesApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:get_profile_choices_api")

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_returns_qos_networks_volumes(self):
        side_effects = [
            (True, [{"name": "qos1"}]),
            (True, [{"name": "net1"}, {"name": "net2"}]),
            (True, [{"name": "vol1"}]),
        ]
        with patch("janus.views.services.get_profiles", side_effect=side_effects):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("qos", data)
        self.assertIn("networks", data)
        self.assertIn("volumes", data)
        self.assertEqual(data["qos"], ["qos1"])
        self.assertEqual(data["networks"], ["net1", "net2"])
        self.assertEqual(data["volumes"], ["vol1"])

    def test_empty_choices(self):
        side_effects = [(True, []), (True, []), (True, [])]
        with patch("janus.views.services.get_profiles", side_effect=side_effects):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["qos"], [])
        self.assertEqual(data["networks"], [])
        self.assertEqual(data["volumes"], [])


class TestCreateProfileApi(TestCase):
    def setUp(self):
        self.staff_user = _make_user(username="admin", is_staff=True)
        self.regular_user = _make_user(username="regular")
        self.url = reverse("janus:create_profile_api", kwargs={"resource": "host"})

    def test_unauthenticated_returns_401(self):
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_non_staff_returns_401(self):
        self.client.force_login(self.regular_user)
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_get_method_returns_405(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(self.url, data="bad-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_staff_can_create_profile(self):
        self.client.force_login(self.staff_user)
        payload = {"name": "myprofile", "settings": {"cpu": 2}}
        with patch("janus.views.services.create_profile", return_value=(True, {"name": "myprofile"})):
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_service_failure_returns_400(self):
        self.client.force_login(self.staff_user)
        payload = {"name": "myprofile"}
        with patch("janus.views.services.create_profile", return_value=(False, "Error")):
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)


class TestUpdateProfileApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:update_profile_api", kwargs={"resource": "host"})

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_get_method_returns_405(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_invalid_json_returns_400(self):
        response = self.client.post(self.url, data="bad-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_valid_update(self):
        payload = {"name": "myprofile", "settings": {"cpu": 4}}
        with patch("janus.views.services.update_profile", return_value=(True, {"name": "myprofile"})):
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_service_failure_returns_400(self):
        payload = {"name": "myprofile"}
        with patch("janus.views.services.update_profile", return_value=(False, "Error")):
            response = self.client.post(self.url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)


class TestDeleteProfileApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:delete_profile_api", kwargs={"resource": "host", "pname": "myprofile"})

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 401)

    def test_delete_profile_success(self):
        with patch("janus.views.services.delete_profile", return_value=(True, {})):
            response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_service_failure_returns_400(self):
        with patch("janus.views.services.delete_profile", return_value=(False, "Error")):
            response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 400)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Log view
# ─────────────────────────────────────────────────────────────────────────────
class TestViewLogApi(TestCase):
    def setUp(self):
        self.user = _make_user()
        self.client.force_login(self.user)
        self.url = reverse("janus:get_logs_api", kwargs={"session_id": 1, "nname": "mynode"})

    def test_unauthenticated_returns_401(self):
        """view_log must reject unauthenticated requests (security fix)."""
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_returns_log_on_success(self):
        log_data = {"log": "container started\ncontainer running"}
        with patch("janus.views.services.get_log", return_value=(True, log_data)):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), log_data)

    def test_returns_error_dict_on_failure(self):
        with patch("janus.views.services.get_log", return_value=(False, {})):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("error", response.json())

    def test_timestamps_param_forwarded_to_service(self):
        with patch("janus.views.services.get_log", return_value=(True, {})) as mock_svc:
            self.client.get(self.url + "?timestamps=true")
        # ts is the 3rd positional arg (index 2)
        call_args = mock_svc.call_args[0]
        self.assertEqual(call_args[2], "true")

    def test_no_timestamps_param_passes_none(self):
        with patch("janus.views.services.get_log", return_value=(True, {})) as mock_svc:
            self.client.get(self.url)
        call_args = mock_svc.call_args[0]
        self.assertIsNone(call_args[2])