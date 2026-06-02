"""
services.py — Orchestration layer for the Globus Service handler.

Responsibilities:
  - Token CRUD (store/retrieve/refresh GlobusToken records)
  - GlobusService state machine transitions
  - Proxy exec commands to the Janus Controller (non-interactive)
  - Build GCS CLI command strings for each wizard step
"""

import json
import logging
import secrets
import shlex
import ssl
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx
import websocket as ws_lib
from django.conf import settings
from django.contrib.auth.models import User

from .models import GlobusService, GlobusToken
from . import gcs_service as gcs

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Janus Controller base URL (reuse from janus.services pattern)
# ---------------------------------------------------------------------------
_ctrl_base = settings.JANUS_CONTROLLER_URL + "api/janus/controller/"


# ---------------------------------------------------------------------------
# CSRF / state helpers
# ---------------------------------------------------------------------------

def generate_state_token() -> str:
    """Generate a cryptographically random state token for OAuth2 CSRF protection."""
    return secrets.token_urlsafe(32)


# ---------------------------------------------------------------------------
# Globus client_id helper
# ---------------------------------------------------------------------------

def _get_globus_client_id() -> str:
    """
    Return the Globus Native App client ID from Django settings.
    Operators must set GLOBUS_CLIENT_ID in their environment / settings.
    """
    client_id = getattr(settings, "GLOBUS_CLIENT_ID", None)
    if not client_id:
        raise RuntimeError(
            "GLOBUS_CLIENT_ID is not configured. "
            "Set it in settings.py or via the GLOBUS_CLIENT_ID environment variable."
        )
    return client_id


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------

def get_or_create_token_record(user: User) -> GlobusToken:
    """Return the GlobusToken for the user, creating an empty one if needed."""
    token, _ = GlobusToken.objects.get_or_create(
        user=user,
        defaults={"token_data": "{}"},
    )
    return token


def store_tokens(user: User, token_data: dict) -> GlobusToken:
    """Persist Globus token data for a user (upsert)."""
    token, _ = GlobusToken.objects.get_or_create(
        user=user,
        defaults={"token_data": "{}"},
    )
    token.set_token_data(token_data)
    token.save()
    return token


def get_valid_access_token(user: User) -> Optional[str]:
    """
    Return a valid access token for the user, refreshing if expired.
    Returns None if no token exists or refresh fails.
    """
    try:
        token_record = GlobusToken.objects.get(user=user)
    except GlobusToken.DoesNotExist:
        return None

    data = token_record.get_token_data()
    if not data.get("access_token"):
        return None

    if token_record.is_expired():
        refresh_token = data.get("refresh_token")
        if not refresh_token:
            return None
        try:
            client_id = _get_globus_client_id()
            new_data = gcs.refresh_tokens(client_id, refresh_token)
            # Preserve refresh_token if not returned in refresh response
            if not new_data.get("refresh_token"):
                new_data["refresh_token"] = refresh_token
            store_tokens(user, new_data)
            return new_data.get("access_token")
        except Exception as exc:
            logger.error("Token refresh failed for user %s: %s", user.username, exc)
            return None

    return data.get("access_token")


def has_valid_tokens(user: User) -> bool:
    """Return True if the user has stored (possibly refreshable) Globus tokens."""
    return get_valid_access_token(user) is not None


def delete_tokens(user: User) -> None:
    """Remove stored Globus tokens for a user."""
    GlobusToken.objects.filter(user=user).delete()


# ---------------------------------------------------------------------------
# OAuth2 flow helpers
# ---------------------------------------------------------------------------

def build_auth_url(redirect_uri: str = None) -> Tuple[str, str, dict]:
    """
    Build a Globus Auth authorization URL using the OOB (out-of-band) flow.

    The OOB flow uses redirect_uri=https://auth.globus.org/v2/web/auth-code so
    that Globus displays the authorization code directly on the page for the user
    to copy and paste — no redirect to our server is needed.

    The redirect_uri parameter is accepted for API compatibility but ignored;
    the OOB URI is always used.

    Returns:
        (auth_url, state, pkce_data) — the authorization URL, CSRF state token,
        and a dict with the PKCE verifier. Store pkce_data in the session and
        pass it back to complete_auth().
    """
    client_id = _get_globus_client_id()
    state = generate_state_token()
    # redirect_uri arg is ignored — gcs.get_auth_url always uses GLOBUS_OOB_REDIRECT_URI
    auth_url, verifier = gcs.get_auth_url(client_id, redirect_uri or "", state)
    pkce_data = {"verifier": verifier} if verifier else {}
    return auth_url, state, pkce_data


def complete_auth(user: User, code: str, redirect_uri: str, pkce_data: Optional[dict] = None) -> dict:
    """
    Exchange an authorization code for tokens and persist them.

    Args:
        user:         The Django user.
        code:         The authorization code from Globus.
        redirect_uri: The redirect URI used in build_auth_url().
        pkce_data:    Dict with 'verifier' from build_auth_url().
                      The verifier is passed to oauth2_start_flow() so globus-sdk
                      recomputes the correct challenge — required for PKCE flows.

    Returns:
        The token data dict.
    Raises:
        Exception on failure.
    """
    client_id = _get_globus_client_id()
    token_data = gcs.exchange_code_for_tokens(client_id, redirect_uri, code, pkce_data=pkce_data)
    store_tokens(user, token_data)
    return token_data


# ---------------------------------------------------------------------------
# GlobusService CRUD
# ---------------------------------------------------------------------------

def create_service(user: User, session_id: int, node_name: str, container_id: str, display_name: str = "") -> GlobusService:
    """Create a new GlobusService record in PENDING state."""
    service = GlobusService.objects.create(
        user=user,
        session_id=session_id,
        node_name=node_name,
        container_id=container_id,
        display_name=display_name,
        status=GlobusService.Status.PENDING,
    )
    logger.info("Created GlobusService id=%s for user=%s", service.pk, user.username)
    return service


def launch_node_container(service: GlobusService, node_name: str, node_setup_args: str = "") -> Tuple[bool, str]:
    """
    Launch a GCS node container via the Janus Controller with DEPLOYMENT_KEY set.

    This creates and starts a new Janus session using the GCS image with the
    deployment key from service.config_data passed as the DEPLOYMENT_KEY env var.
    The container's /entrypoint.sh reads DEPLOYMENT_KEY, runs node setup, and
    starts all GCS services (GCS Manager, Apache, GridFTP).

    Args:
        service:        The GlobusService record (must have deployment_key in config_data).
        node_name:      The Janus node name to launch on.
        node_setup_args: Optional NODE_SETUP_ARGS override (e.g. --ip-address ...).
                         If empty, uses the profile's default NODE_SETUP_ARGS.

    Returns:
        (success, message) — on success, message contains the new container_id.
    """
    GCS_IMAGE = "dtnaas/globus-connect-server:debian-12-5.4.79"
    GCS_PROFILE = "globus-gcs-test"

    # Get the deployment key from service config_data
    config = service.get_config_data()
    deployment_key = config.get("deployment_key", "")
    if not deployment_key:
        return False, "No deployment key found. Complete endpoint setup first."

    # Build kwargs for the Janus Controller session create
    kwargs = {"DEPLOYMENT_KEY": deployment_key}
    if node_setup_args:
        kwargs["NODE_SETUP_ARGS"] = node_setup_args

    create_data = {
        "errors": [],
        "instances": [node_name],
        "image": GCS_IMAGE,
        "profile": GCS_PROFILE,
        "kwargs": kwargs,
        "remove_container": False,
        "name": f"gcs-node-{service.pk}",
    }

    try:
        # Step 1: Create the session
        res = httpx.post(
            url=_ctrl_base + "create",
            json=create_data,
            auth=settings.JANUS_CONTROLLER_AUTH,
            verify=settings.CTRL_SSL_VERIFY,
            timeout=30.0,
        )
        if res.status_code != 200:
            return False, f"Session create failed: {res.text}"
        create_resp = res.json()
        session_id = int(list(create_resp.keys())[0])
        logger.info("GlobusService id=%s: node session created, id=%s", service.pk, session_id)

        # Step 2: Start the session
        res = httpx.put(
            url=_ctrl_base + f"start/{session_id}",
            auth=settings.JANUS_CONTROLLER_AUTH,
            verify=settings.CTRL_SSL_VERIFY,
            timeout=60.0,
        )
        if res.status_code != 200:
            return False, f"Session start failed: {res.text}"
        start_resp = res.json()

        # Step 3: Extract container ID
        session_data = start_resp.get(str(session_id), {})
        services_map = session_data.get("services", {})
        container_id = ""
        actual_node = node_name
        for nname, svcs in services_map.items():
            actual_node = nname
            for svc in svcs:
                errors = svc.get("errors", [])
                if errors:
                    return False, f"Container launch errors: {errors}"
                container_id = svc.get("container_id", "")
                break
            if container_id:
                break

        if not container_id:
            return False, "No container_id in start response"

        # Step 4: Update service to point to the node container
        service.session_id = session_id
        service.node_name = actual_node
        service.container_id = container_id
        _transition(service, GlobusService.Status.NODE_CONFIGURED)
        logger.info(
            "GlobusService id=%s: node container launched, container=%s",
            service.pk, container_id[:12],
        )
        return True, container_id

    except Exception as exc:
        logger.error("launch_node_container failed: %s", exc)
        return False, str(exc)


def get_service(service_id: int, user: User) -> Optional[GlobusService]:
    """Return a GlobusService owned by the given user, or None."""
    try:
        return GlobusService.objects.get(pk=service_id, user=user)
    except GlobusService.DoesNotExist:
        return None


def list_services(user: User) -> list:
    """Return all GlobusService records for the user as dicts."""
    return [s.to_dict() for s in GlobusService.objects.filter(user=user)]


def delete_service(service_id: int, user: User) -> bool:
    """Delete a GlobusService. Returns True if deleted, False if not found."""
    deleted, _ = GlobusService.objects.filter(pk=service_id, user=user).delete()
    return deleted > 0


def _transition(service: GlobusService, new_status: str, error_msg: str = "") -> None:
    """Update service status and optionally set an error message."""
    service.status = new_status
    if error_msg:
        service.error_message = error_msg
    service.save()


# ---------------------------------------------------------------------------
# Janus Controller exec proxy
# ---------------------------------------------------------------------------

def _exec_in_container(node_name: str, container_id: str, cmd: str, timeout: float = 120.0) -> Tuple[bool, str]:
    """
    Execute a command inside a running container via the Janus Controller exec API
    and collect its output via the Janus Controller WebSocket stream.

    The Janus Controller exec REST endpoint only returns an exec ID ({"Id": "..."}).
    The actual stdout/stderr output is streamed via the WebSocket at /ws with
    message type 0 (exec stream). This function:
      1. Creates the exec via POST /exec (start=False, attach=True, tty=False)
      2. Opens the controller WebSocket
      3. Sends the exec start message
      4. Collects all output until the stream closes
      5. Returns the combined output

    Args:
        node_name:    The Janus node name (e.g. "benki").
        container_id: The full container ID on that node.
        cmd:          Shell command string to execute.
        timeout:      Seconds to wait for output before giving up.

    Returns:
        (success: bool, output: str) — combined stdout/stderr output.
    """
    # Step 1: Create the exec (start=False so we can attach via WS first)
    data = {
        "node": node_name,
        "container": container_id,
        "Cmd": shlex.split(cmd),
        "attach": True,
        "tty": False,
        "start": False,
    }
    try:
        res = httpx.post(
            url=_ctrl_base + "exec",
            json=data,
            auth=settings.JANUS_CONTROLLER_AUTH,
            verify=settings.CTRL_SSL_VERIFY,
            timeout=30.0,
        )
        if res.status_code not in (200, 201):
            try:
                err = res.json()
            except Exception:
                err = {"error": res.text or f"HTTP {res.status_code}"}
            return False, json.dumps(err)

        body = res.json()
        exec_id = body.get("Id")
        node_id = body.get("node_id", "")
        if not exec_id:
            return False, "No exec ID returned from controller"

    except Exception as exc:
        logger.error("exec_in_container: create exec failed: %s", exc)
        return False, str(exc)

    # Step 2: Connect to the controller WebSocket and stream output
    ws_url = f"{settings.JANUS_CONTROLLER_WS_URL}/ws"
    output_parts = []
    try:
        ctrl_ws = ws_lib.create_connection(
            ws_url,
            sslopt={"cert_reqs": ssl.CERT_NONE},
            timeout=timeout,
        )
        # Send exec start message (type 0 = exec stream)
        start_msg = {
            "type": 0,
            "node": node_name,
            "node_id": node_id,
            "container": container_id,
            "exec_id": exec_id,
        }
        ctrl_ws.send(json.dumps(start_msg))

        # Collect output until stream closes
        while True:
            try:
                ctrl_ws.settimeout(timeout)
                raw = ctrl_ws.recv()
                if raw:
                    output_parts.append(raw)
            except ws_lib.WebSocketTimeoutException:
                logger.warning("exec_in_container: WebSocket timeout after %ss", timeout)
                break
            except Exception:
                break

        ctrl_ws.close()
    except Exception as exc:
        logger.error("exec_in_container: WebSocket stream failed: %s", exc)
        # Return whatever we collected so far, but mark as failed if nothing
        combined = "".join(output_parts)
        return bool(combined), combined or str(exc)

    combined = "".join(output_parts)
    logger.debug("exec_in_container output (%d chars): %s", len(combined), combined[:200])
    return True, combined


# ---------------------------------------------------------------------------
# GCS CLI command builders
# ---------------------------------------------------------------------------

def _build_endpoint_setup_cmd(config: dict) -> str:
    """
    Build the `globus-connect-server endpoint setup` command.

    Expected config keys:
        display_name          — endpoint display name (required)
        organization          — organization name (required)
        contact_email         — contact email (required)
        owner                 — Globus identity username (e.g. user@globusid.org).
                                Only included in the command if explicitly provided.
                                Do NOT default to the service account here — the GCS CLI
                                uses the endpoint's own client credentials to contact Globus
                                Auth for the ownership transfer, and those credentials may
                                not match the service account. Use `endpoint set-owner`
                                separately after setup if needed.
        project_id            — existing Globus project UUID (optional)
        always_create_project — bool; pass --always-create-project when True and no project_id
        deployment_key_path   — path inside container to write deployment key
                                (default: /work/deployment-key.json)

    Notes from real-world usage:
        - --agree-to-letsencrypt-tos is required
        - -d <path> writes the deployment key JSON for later use as DEPLOYMENT_KEY env var
        - Either --project-id or --always-create-project must be supplied
        - This command is interactive: it prints a Globus Auth URL and waits for a code.
          Run it via the GCSInteractiveConsumer WebSocket, not the non-interactive exec API.
    """
    display_name = shlex.quote(config.get("display_name", "My GCS Endpoint"))
    organization = shlex.quote(config.get("organization", ""))
    contact_email = shlex.quote(config.get("contact_email", ""))
    # Only include --owner if explicitly provided by the caller
    owner = config.get("owner", "")
    project_id = config.get("project_id", "")
    always_create_project = config.get("always_create_project", True)
    deployment_key_path = config.get("deployment_key_path", "/work/deployment-key.json")

    gcs_cmd = (
        f"globus-connect-server endpoint setup"
        f" --organization {organization}"
        f" --contact-email {contact_email}"
        f" --agree-to-letsencrypt-tos"
        f" -d {shlex.quote(deployment_key_path)}"
    )
    if owner:
        gcs_cmd += f" --owner {shlex.quote(owner)}"
    if project_id:
        gcs_cmd += f" --project-id {shlex.quote(project_id)}"
    elif always_create_project:
        gcs_cmd += " --always-create-project"
    gcs_cmd += f" {display_name}"

    # After endpoint setup succeeds, immediately transfer ownership to the service account
    # using the GCS CLI.  This must happen in the same shell session while the GCS CLI
    # credentials (stored in /root/.globus_connect_server/) are still valid.
    # The REST API approach fails because the service account has no role yet.
    service_identity = getattr(settings, "GLOBUS_SERVICE_IDENTITY", "")
    set_owner_cmd = ""
    if service_identity:
        set_owner_cmd = (
            f" && globus-connect-server endpoint set-owner {shlex.quote(service_identity)}"
        )

    # Wrap in bash -c so the shell interprets the cleanup + setup + set-owner as one session.
    # Cleanup removes:
    #   - stale GCS config dirs (prevent "client_id and secret already exist" error)
    #   - the old deployment key on the shared /work volume (same error if left behind)
    # Use double-quotes for the outer bash -c wrapper so that single-quoted display
    # names inside gcs_cmd are not broken.
    full_cmd = (
        f'bash -c "rm -rf /etc/globus-connect-server/* /var/lib/globus-connect-server/*'
        f' {shlex.quote(deployment_key_path)} 2>/dev/null; {gcs_cmd}{set_owner_cmd}"'
    )
    return full_cmd


def _build_gcs_login_cmd(endpoint_id: str) -> str:
    """
    Build the `globus-connect-server login <endpoint-id>` command.

    This is interactive — it prints a Globus Auth URL and waits for a code.
    Must be run via GCSInteractiveConsumer WebSocket, not the non-interactive exec API.
    Required before storage-gateway and collection creation.
    """
    return f"globus-connect-server login {shlex.quote(endpoint_id)}"


def _build_endpoint_set_owner_cmd(service_account_id: str, use_explicit_host: str = "") -> str:
    """
    Build the `globus-connect-server endpoint set-owner` command.

    Per real-world usage, ownership must be transferred to a service account
    (e.g. janus-webapp-service-account@clients.auth.globus.org) before
    storage gateway creation so the gateway can be managed programmatically.

    Args:
        service_account_id: Globus client ID of the service account,
                            e.g. "68c19eed-8872-4107-b85c-e11be12db9ad@clients.auth.globus.org"
        use_explicit_host:  If non-empty, appends ``--use-explicit-host <ip>`` so the
                            CLI connects to the GCS Manager at that IP address instead of
                            trying to resolve the public hostname.  Required when running
                            inside the node container where the public GCS hostname does
                            not resolve (e.g. ``"127.0.0.1"``).
    """
    cmd = f"globus-connect-server endpoint set-owner {shlex.quote(service_account_id)}"
    if use_explicit_host:
        cmd += f" --use-explicit-host {shlex.quote(use_explicit_host)}"
    return cmd


def _build_storage_gateway_cmd(config: dict) -> str:
    """
    Build the `globus-connect-server storage-gateway create` command.

    Expected config keys:
        connector             — posix | s3 | ... (required)
        display_name          — human-readable name (required)
        gateway_name          — internal identifier (required)
        domain                — Globus Auth domain to restrict access (e.g. es.net)
        user_deny             — comma-separated local users to deny (default: "root")
        restrict_paths_file   — path inside container to a path-restrictions JSON file
                                (e.g. /work/path-restrictions.json); preferred form.
                                Takes precedence over restrict_paths list.
        restrict_paths        — list of read_write paths (fallback if no restrict_paths_file)

    Notes from real-world usage:
        - Positional arg order: connector, display_name, gateway_name
        - --restrict-paths file:/work/path-restrictions.json is the preferred form
        - --user-deny root is commonly required
        - path-restrictions.json format:
            {"DATA_TYPE": "path_restrictions#1.0.0", "read_write": ["/data/ESnet"]}
        - Run `globus-connect-server login <endpoint-id>` (interactive) before this step
    """
    connector = config.get("connector", "posix")
    display_name = shlex.quote(config.get("display_name", "My Storage Gateway"))
    domain = config.get("domain", "")
    gateway_name = shlex.quote(config.get("gateway_name", "default"))
    user_deny = config.get("user_deny", "root")
    restrict_paths_file = config.get("restrict_paths_file", "")

    # Note: `storage-gateway create <connector>` takes DISPLAY_NAME as the only
    # positional argument. There is no separate gateway_name positional argument.
    cmd = (
        f"globus-connect-server storage-gateway create {shlex.quote(connector)}"
        f" {display_name}"
    )
    if domain:
        cmd += f" --domain {shlex.quote(domain)}"
    if user_deny:
        for u in [u.strip() for u in user_deny.split(",") if u.strip()]:
            cmd += f" --user-deny {shlex.quote(u)}"
    if restrict_paths_file:
        cmd += f" --restrict-paths file:{shlex.quote(restrict_paths_file)}"
    else:
        restrict_paths = config.get("restrict_paths", [])
        for path in restrict_paths:
            cmd += f" --restrict-paths {shlex.quote(path)}"

    return cmd


def _build_collection_create_cmd(config: dict) -> str:
    """
    Build the `globus-connect-server collection create` command.

    Expected config keys:
        storage_gateway_id          — UUID of the storage gateway (required)
        base_path                   — root path on the storage backend (required)
        display_name                — collection display name (required)
        description                 — optional description
        organization                — optional organization
        contact_email               — optional contact email
        keywords                    — optional comma-separated keywords
        enable_anonymous_writes     — bool; add --enable-anonymous-writes if True
        sharing_restrict_paths_file — path inside container to sharing-restrictions JSON
                                      (e.g. /work/sharing-restrictions.json)

    Notes from real-world usage:
        - Positional arg order: storage_gateway_id, base_path, display_name
        - Read-only: --sharing-restrict-paths file:sharing-restrictions.json
          where file = {"DATA_TYPE":"path_restrictions#1.0.0","read":["/"]}
        - Read-write: --enable-anonymous-writes
          --sharing-restrict-paths file:sharing-restriction-rw.json
          where file = {"DATA_TYPE":"path_restrictions#1.0.0","read_write":["/data/..."]}
    """
    storage_gateway_id = shlex.quote(config.get("storage_gateway_id", ""))
    base_path = shlex.quote(config.get("base_path", "/"))
    display_name = shlex.quote(config.get("display_name", "My Collection"))
    description = config.get("description", "")
    organization = config.get("organization", "")
    contact_email = config.get("contact_email", "")
    keywords = config.get("keywords", "")
    enable_anonymous_writes = config.get("enable_anonymous_writes", False)
    sharing_restrict_paths_file = config.get("sharing_restrict_paths_file", "")

    cmd = (
        f"globus-connect-server collection create"
        f" {storage_gateway_id}"
        f" {base_path}"
        f" {display_name}"
    )
    if description:
        cmd += f" --description {shlex.quote(description)}"
    if organization:
        cmd += f" --organization {shlex.quote(organization)}"
    if contact_email:
        cmd += f" --contact-email {shlex.quote(contact_email)}"
    if keywords:
        cmd += f" --keywords {shlex.quote(keywords)}"
    if enable_anonymous_writes:
        cmd += " --enable-anonymous-writes"
    if sharing_restrict_paths_file:
        cmd += f" --sharing-restrict-paths file:{shlex.quote(sharing_restrict_paths_file)}"

    return cmd


# ---------------------------------------------------------------------------
# Wizard step orchestration
# ---------------------------------------------------------------------------

def run_endpoint_setup(service: GlobusService, config: dict) -> Tuple[bool, str]:
    """
    Step 2: Run `globus-connect-server endpoint setup` inside the container.

    IMPORTANT: This command is interactive — it prints a Globus Auth URL and waits
    for the user to paste an authorization code. It must be driven via the
    GCSInteractiveConsumer WebSocket (ws/gcs-interactive/<id>/), not this function.

    This function builds and returns the command string for display/reference,
    and can be used for non-interactive re-runs if the container supports it.
    After the interactive run completes, call fetch_deployment_key() to retrieve
    the deployment-key.json, then store it in config_data for node container launch.

    Updates service status to ENDPOINT_CONFIGURED on success.
    Merges config into service.config_data.
    """
    service.merge_config_data({"endpoint": config})
    if config.get("display_name"):
        service.display_name = config["display_name"]
    service.save()

    cmd = _build_endpoint_setup_cmd(config)
    logger.info("GlobusService id=%s: endpoint setup cmd (interactive): %s", service.pk, cmd)
    # Return the command for the caller to run interactively via WebSocket
    return True, cmd


def _run_endpoint_set_owner_in_container(service: GlobusService) -> Tuple[bool, str]:
    """
    Run `globus-connect-server endpoint set-owner <service_account_id>` inside the
    setup container to transfer endpoint ownership to the Janus service account.

    This must be called while the setup container is still running and has the
    endpoint credentials stored from the `endpoint setup` run.  The GCS CLI uses
    those stored credentials (which have the correct manage_collections scope) to
    authorize the ownership transfer — no additional login or user token needed.

    This is non-fatal: if it fails (e.g. container stopped, credentials expired),
    a warning is logged and the wizard continues.  The user can manually transfer
    ownership later via the Globus web UI or `grant-admin` API endpoint.

    Returns:
        (success, message)
    """
    service_identity = getattr(settings, "GLOBUS_SERVICE_IDENTITY", "")
    if not service_identity:
        logger.warning(
            "GlobusService id=%s: GLOBUS_SERVICE_IDENTITY not configured — skipping set-owner",
            service.pk,
        )
        return False, "GLOBUS_SERVICE_IDENTITY not configured."

    cmd = f"globus-connect-server endpoint set-owner {shlex.quote(service_identity)}"
    logger.info(
        "GlobusService id=%s: running endpoint set-owner in setup container: %s",
        service.pk, cmd,
    )
    try:
        success, output = _exec_in_container(
            service.node_name, service.container_id, cmd, timeout=30.0
        )
        if success and output.strip():
            logger.info(
                "GlobusService id=%s: endpoint set-owner output: %s",
                service.pk, output.strip()[:200],
            )
        if not success or "error" in output.lower() or "Error" in output:
            logger.warning(
                "GlobusService id=%s: endpoint set-owner may have failed: %s",
                service.pk, output.strip()[:200],
            )
            return False, output.strip()
        logger.info(
            "GlobusService id=%s: endpoint ownership transferred to %s via CLI",
            service.pk, service_identity,
        )
        return True, output.strip()
    except Exception as exc:
        logger.warning(
            "GlobusService id=%s: endpoint set-owner failed (non-fatal): %s",
            service.pk, exc,
        )
        return False, str(exc)


def fetch_deployment_key(service: GlobusService, deployment_key_path: str = "/work/deployment-key.json") -> Tuple[bool, str]:
    """
    Retrieve the deployment-key.json from the container after endpoint setup.

    The deployment key is written by `globus-connect-server endpoint setup -d <path>`.
    It must be collected and stored so it can be passed as the DEPLOYMENT_KEY
    environment variable when launching the node container.

    Also derives and stores the gcs_address (<endpoint_id>.data.globus.org) in
    config_data so the service account REST API can reach the GCS Manager.

    Returns:
        (success, deployment_key_json_string)
    """
    cmd = f"cat {shlex.quote(deployment_key_path)}"
    logger.info("GlobusService id=%s: fetching deployment key from %s", service.pk, deployment_key_path)
    success, output = _exec_in_container(service.node_name, service.container_id, cmd)

    if success and output.strip():
        key_str = output.strip()
        # Store the deployment key in config_data for later use
        existing = service.get_config_data()
        existing["deployment_key"] = key_str
        existing.setdefault("endpoint", {})["deployment_key_path"] = deployment_key_path

        # Try to extract the endpoint ID from the deployment key JSON
        # The deployment key contains an "endpoint_id" field
        try:
            import json as _json
            key_data = _json.loads(key_str)
            endpoint_id = key_data.get("endpoint_id", "")
            if endpoint_id and not service.globus_endpoint_id:
                service.globus_endpoint_id = endpoint_id
                logger.info(
                    "GlobusService id=%s: extracted endpoint_id=%s from deployment key",
                    service.pk, endpoint_id,
                )
        except Exception:
            pass

        # If still no endpoint ID, try running `globus-connect-server endpoint show`
        if not service.globus_endpoint_id:
            _, ep_output = _exec_in_container(
                service.node_name, service.container_id,
                "bash -c \"globus-connect-server endpoint show 2>&1 | grep -i 'endpoint id' | head -1\""
            )
            ep_id = _extract_endpoint_id(ep_output)
            if ep_id:
                service.globus_endpoint_id = ep_id
                logger.info(
                    "GlobusService id=%s: extracted endpoint_id=%s from endpoint show",
                    service.pk, ep_id,
                )

        # Derive and store the GCS Manager address for service account API calls
        if service.globus_endpoint_id:
            gcs_address = gcs.derive_gcs_address(service.globus_endpoint_id)
            existing["gcs_address"] = gcs_address
            logger.info(
                "GlobusService id=%s: derived gcs_address=%s",
                service.pk, gcs_address,
            )

        service.set_config_data(existing)
        _transition(service, GlobusService.Status.ENDPOINT_CONFIGURED)
        logger.info("GlobusService id=%s: deployment key collected successfully", service.pk)

        # Transfer endpoint ownership to the service account by running
        # `globus-connect-server endpoint set-owner` inside the setup container.
        # This uses the stored endpoint credentials (from endpoint setup) which have
        # the correct manage_collections scope — no additional login needed.
        # The REST API approach (transfer_endpoint_ownership) requires the caller to
        # already have a role, which the service account doesn't have yet.
        # This is non-fatal — log a warning if it fails but don't block the wizard.
        _run_endpoint_set_owner_in_container(service)
    else:
        logger.warning("GlobusService id=%s: could not fetch deployment key: %s", service.pk, output)

    return success, output


def get_gcs_login_cmd(service: GlobusService) -> str:
    """
    Return the combined GCS login + ownership-transfer command for Step 3.5.

    The command runs interactively in the **node container** via the
    GCSInteractiveConsumer WebSocket.  It:

    1. Runs ``globus-connect-server login <endpoint-id>`` — this is interactive:
       GCS prints a Globus Auth URL, the user opens it, authenticates, and pastes
       the resulting code back into the terminal.  This populates the GCS Manager's
       role database so that subsequent REST API calls (gateway/collection creation)
       are authorised.

    2. If ``GLOBUS_SERVICE_IDENTITY`` is configured, chains
       ``globus-connect-server endpoint set-owner <identity>`` so that the service
       account becomes the endpoint owner immediately after login.

    The endpoint_id must have been set on the service (from endpoint setup output).
    """
    endpoint_id = service.globus_endpoint_id
    if not endpoint_id:
        raise ValueError(
            f"GlobusService id={service.pk} has no endpoint_id. "
            "Complete endpoint setup first."
        )
    login_cmd = _build_gcs_login_cmd(endpoint_id)
    service_identity = getattr(settings, "GLOBUS_SERVICE_IDENTITY", "")
    if service_identity:
        # Pass --use-explicit-host 127.0.0.1 so the CLI connects to the GCS
        # Manager at the local IP rather than trying to resolve the public
        # hostname (e.g. 002d5a.69a6.gaccess.io) which doesn't resolve from
        # inside the node container.
        set_owner_cmd = _build_endpoint_set_owner_cmd(
            service_identity, use_explicit_host="127.0.0.1"
        )
        # The Docker exec API does NOT invoke a shell, so `&&` would be passed
        # as a literal argument to `globus-connect-server login`.  Wrap the
        # chained command in `bash -c "..."` so the shell interprets `&&`.
        return f'bash -c "{login_cmd} && {set_owner_cmd}"'
    return login_cmd


def transfer_endpoint_ownership(service: GlobusService) -> Tuple[bool, str]:
    """
    Transfer endpoint ownership to the Janus service account via the GCS REST API.

    Called automatically after deployment key collection.  The PUT to
    /api/endpoint/owner must be authorized by the **current endpoint owner**
    (the human user who ran ``endpoint setup --owner <user>``), not the service
    account.  We use the user's stored Globus access token for this call, then
    the service account becomes the new owner.

    Returns:
        (success, message)
    """
    gcs_address, endpoint_id, verify_tls, local_address = _resolve_gcs_connection(service)
    if not gcs_address or not endpoint_id:
        return False, "endpoint_id / gcs_address not set — cannot transfer ownership."

    service_client_id = getattr(settings, "GLOBUS_SERVICE_CLIENT_ID", "")
    if not service_client_id:
        return False, "GLOBUS_SERVICE_CLIENT_ID not configured."

    # Use the user's access token — the user is the current endpoint owner and
    # must authorize the ownership transfer.  The service account token would
    # get 403 because it has no role on the endpoint yet.
    access_token = get_valid_access_token(service.user)
    if not access_token:
        return False, "No valid user access token — cannot authorize ownership transfer."

    try:
        gcs.set_endpoint_owner_via_api(
            gcs_address, service_client_id, access_token,
            verify_tls=verify_tls, local_address=local_address,
        )
        logger.info(
            "GlobusService id=%s: endpoint ownership transferred to service account %s",
            service.pk, service_client_id,
        )
        return True, "Endpoint ownership transferred to service account."
    except Exception as exc:
        logger.warning(
            "GlobusService id=%s: ownership transfer failed (non-fatal): %s",
            service.pk, exc,
        )
        return False, str(exc)


def grant_user_admin_role(service: GlobusService, user_identity_id: str) -> Tuple[bool, str]:
    """
    Grant a Globus identity the 'administrator' role on the endpoint.

    Called after ownership transfer so the human user retains management access
    in the Globus web UI even though the service account is the owner.

    Args:
        service:          The GlobusService record.
        user_identity_id: Globus identity UUID of the user to grant admin to.

    Returns:
        (success, message)
    """
    gcs_address, endpoint_id, verify_tls, local_address = _resolve_gcs_connection(service)
    if not gcs_address or not endpoint_id:
        return False, "endpoint_id / gcs_address not set."

    try:
        client = gcs.get_gcs_client_service_account(gcs_address, endpoint_id, verify_tls=verify_tls, local_address=local_address)
        gcs.create_role(client, endpoint_id, user_identity_id, role="administrator")
        logger.info(
            "GlobusService id=%s: granted administrator role to identity %s",
            service.pk, user_identity_id,
        )
        return True, f"Administrator role granted to {user_identity_id}."
    except Exception as exc:
        logger.warning(
            "GlobusService id=%s: grant admin role failed (non-fatal): %s",
            service.pk, exc,
        )
        return False, str(exc)


def set_endpoint_owner(service: GlobusService, service_account_id: str) -> Tuple[bool, str]:
    """
    Run `globus-connect-server endpoint set-owner <service_account_id>`.

    Per real-world usage, ownership must be transferred to a service account
    before storage gateway creation so the gateway can be managed programmatically.

    This command is interactive (requires prior `gcs login`). Run it via
    GCSInteractiveConsumer WebSocket after completing the login step.

    Returns the command string for the caller to send via the interactive session.
    """
    cmd = _build_endpoint_set_owner_cmd(service_account_id)
    logger.info("GlobusService id=%s: set-owner cmd: %s", service.pk, cmd)
    return True, cmd


def run_node_setup(service: GlobusService, config: dict) -> Tuple[bool, str]:
    """
    Step 3: Node setup is performed by launch_node_container() via the container
    entrypoint (/entrypoint.sh reads DEPLOYMENT_KEY and runs node setup automatically).

    This function is kept for API compatibility but does NOT call a separate
    node-setup CLI command — that would be a NameError since _build_node_setup_cmd
    does not exist.  The node container handles setup on its own at startup.

    Updates service status to NODE_CONFIGURED.
    """
    service.merge_config_data({"node": config})
    _transition(service, GlobusService.Status.NODE_CONFIGURED)
    return True, "Node setup is handled by the container entrypoint."


def derive_gcs_address(endpoint_id: str) -> str:
    """Return the GCS Manager FQDN for an endpoint UUID."""
    return gcs.derive_gcs_address(endpoint_id)


def _resolve_gcs_connection(service: GlobusService):
    """
    Return (gcs_address, endpoint_id, verify_tls, local_address) for service account REST calls.

    In local/NAT environments, the GCS Manager is reachable at 127.0.0.1 but its
    Apache vhost is configured for its own hostname (e.g. ``062b47.6fbd.gaccess.io``),
    stored as ``gcs_manager_hostname`` in config_data.  We must use that hostname as
    the URL (and Host header) while directing TCP to 127.0.0.1.

    Resolution order for gcs_address:
      1. ``gcs_manager_hostname`` (actual GCS Manager hostname from TLS cert CN) — used
         when ``gcs_local_address`` is also set (local/NAT mode).
      2. ``gcs_address`` (public Globus Transfer alias, e.g. ``<uuid>.data.globus.org``).
      3. Derived from endpoint_id as ``<uuid>.data.globus.org``.

    Returns:
        (gcs_address, endpoint_id, verify_tls, local_address)
        or (None, None, True, "") if endpoint_id is not configured.
    """
    cfg = service.get_config_data()
    endpoint_id = service.globus_endpoint_id
    if not endpoint_id:
        return None, None, True, ""

    public_address = cfg.get("gcs_address") or gcs.derive_gcs_address(endpoint_id)
    local_address = cfg.get("gcs_local_address", "").strip()
    manager_hostname = cfg.get("gcs_manager_hostname", "").strip()

    if local_address:
        # Use the GCS Manager's actual hostname (from TLS cert CN) as the URL/Host header,
        # with TCP directed to the local IP.  Fall back to public_address if not discovered.
        effective_address = manager_hostname or public_address
        logger.debug(
            "GlobusService id=%s: local mode — gcs_address=%s via %s (verify_tls=False)",
            service.pk, effective_address, local_address,
        )
        return effective_address, endpoint_id, False, local_address
    return public_address, endpoint_id, True, ""


def create_gateway_via_api(service: GlobusService, config: dict) -> Tuple[bool, str]:
    """
    Step 4: Create a storage gateway via the GCS REST API using the service account.

    Uses ConfidentialAppAuthClient + ClientCredentialsAuthorizer so no interactive
    GCS login is required.

    Updates service status to GATEWAY_CONFIGURED on success.
    Stores the gateway_id in config_data.
    """
    service.merge_config_data({"storage_gateway": config})
    service.save()

    gcs_address, endpoint_id, verify_tls, local_address = _resolve_gcs_connection(service)
    if not gcs_address or not endpoint_id:
        msg = "endpoint_id and gcs_address are required for service account gateway creation."
        _transition(service, GlobusService.Status.ERROR, error_msg=msg)
        return False, msg

    try:
        client = gcs.get_gcs_client_service_account(gcs_address, endpoint_id, verify_tls=verify_tls, local_address=local_address)
        connector_name = config.get("connector", "posix")
        connector_id = gcs.get_connector_id(connector_name)
        if not connector_id:
            msg = f"Unknown connector: {connector_name}"
            _transition(service, GlobusService.Status.ERROR, error_msg=msg)
            return False, msg

        gateway_data = {
            "connector_id": connector_id,
            "display_name": config.get("display_name", "Storage Gateway"),
        }
        if config.get("allowed_domains"):
            gateway_data["allowed_domains"] = config["allowed_domains"]

        # users_deny: list of local usernames to deny (e.g. ["root"])
        if config.get("users_deny"):
            gateway_data["users_deny"] = config["users_deny"]

        # restrict_paths: inline path restrictions dict
        # Expected shape: {"none": [...], "read": [...], "read_write": [...]}
        # DATA_TYPE is added by create_storage_gateway() if missing.
        if config.get("restrict_paths"):
            gateway_data["restrict_paths"] = config["restrict_paths"]

        result = gcs.create_storage_gateway(client, gateway_data)
        gateway_id = result.get("id", "")
        if gateway_id:
            existing = service.get_config_data()
            existing.setdefault("storage_gateway", {})["id"] = gateway_id
            service.set_config_data(existing)
            service.save()
        _transition(service, GlobusService.Status.GATEWAY_CONFIGURED)
        logger.info("GlobusService id=%s: gateway created via API, id=%s", service.pk, gateway_id)
        return True, gateway_id
    except Exception as exc:
        msg = str(exc) or repr(exc)
        logger.error(
            "GlobusService id=%s: gateway create via API failed: %r (type=%s)",
            service.pk, exc, type(exc).__name__,
            exc_info=True,
        )
        _transition(service, GlobusService.Status.ERROR, error_msg=msg)
        return False, msg


def create_collection_via_api(service: GlobusService, config: dict) -> Tuple[bool, str]:
    """
    Step 5: Create a mapped or guest collection via the GCS REST API using the service account.

    For mapped collections: creates a MappedCollectionDocument directly.
    For guest collections: first creates a UserCredentialDocument, then a GuestCollectionDocument.

    Updates service status to COLLECTIONS_CONFIGURED on success.
    Stores the collection_id in config_data.
    """
    service.merge_config_data({"collection": config})
    service.save()

    cfg = service.get_config_data()
    gcs_address, endpoint_id, verify_tls, local_address = _resolve_gcs_connection(service)
    if not gcs_address or not endpoint_id:
        msg = "endpoint_id and gcs_address are required for service account collection creation."
        _transition(service, GlobusService.Status.ERROR, error_msg=msg)
        return False, msg

    collection_type = config.get("collection_type", "mapped")

    try:
        client = gcs.get_gcs_client_service_account(gcs_address, endpoint_id, verify_tls=verify_tls, local_address=local_address)

        if collection_type == "guest":
            # Guest collection: need UserCredential first, then GuestCollectionDocument
            storage_gateway_id = config.get("storage_gateway_id") or cfg.get("storage_gateway", {}).get("id", "")
            mapped_collection_id = config.get("mapped_collection_id", "")
            identity_id = getattr(settings, "GLOBUS_SERVICE_CLIENT_ID", "")
            local_username = config.get("local_username", "globus")

            if not storage_gateway_id:
                msg = "storage_gateway_id is required for guest collection creation."
                _transition(service, GlobusService.Status.ERROR, error_msg=msg)
                return False, msg
            if not mapped_collection_id:
                msg = "mapped_collection_id is required for guest collection creation."
                _transition(service, GlobusService.Status.ERROR, error_msg=msg)
                return False, msg

            # Create user credential
            gcs.create_user_credential(client, storage_gateway_id, identity_id, local_username)
            logger.info("GlobusService id=%s: user credential created", service.pk)

            # Create guest collection
            result = gcs.create_guest_collection(
                client,
                mapped_collection_id=mapped_collection_id,
                base_path=config.get("base_path", "/"),
                display_name=config.get("display_name", "Guest Collection"),
            )
        else:
            # Mapped collection
            storage_gateway_id = config.get("storage_gateway_id") or cfg.get("storage_gateway", {}).get("id", "")
            collection_data = {
                "collection_base_path": config.get("base_path", "/"),
                "display_name": config.get("display_name", "Mapped Collection"),
            }
            if storage_gateway_id:
                collection_data["storage_gateway_id"] = storage_gateway_id
            result = gcs.create_collection(client, collection_data)

        collection_id = result.get("id", "")
        if collection_id:
            existing = service.get_config_data()
            existing.setdefault("collection", {})["id"] = collection_id
            service.set_config_data(existing)
            service.save()
        _transition(service, GlobusService.Status.COLLECTIONS_CONFIGURED)
        logger.info("GlobusService id=%s: collection created via API, id=%s", service.pk, collection_id)
        return True, collection_id
    except Exception as exc:
        msg = str(exc)
        logger.error("GlobusService id=%s: collection create via API failed: %s", service.pk, msg)
        _transition(service, GlobusService.Status.ERROR, error_msg=msg)
        return False, msg


# ---------------------------------------------------------------------------
# Legacy CLI-based gateway/collection functions (kept for backward compat)
# ---------------------------------------------------------------------------

def run_storage_gateway_create(service: GlobusService, config: dict) -> Tuple[bool, str]:
    """
    Legacy: Run `globus-connect-server storage-gateway create` inside the container.
    Prefer create_gateway_via_api() for new code.
    """
    service.merge_config_data({"storage_gateway": config})
    service.save()

    cmd = _build_storage_gateway_cmd(config)
    logger.info("GlobusService id=%s: running storage-gateway create: %s", service.pk, cmd)
    success, output = _exec_in_container(service.node_name, service.container_id, cmd)

    if success:
        gateway_id = _extract_uuid(output)
        if gateway_id:
            existing = service.get_config_data()
            existing.setdefault("storage_gateway", {})["id"] = gateway_id
            service.set_config_data(existing)
            service.save()
        _transition(service, GlobusService.Status.GATEWAY_CONFIGURED)
    else:
        _transition(service, GlobusService.Status.ERROR, error_msg=output)

    return success, output


def run_collection_create(service: GlobusService, config: dict) -> Tuple[bool, str]:
    """
    Legacy: Run `globus-connect-server collection create` inside the container.
    Prefer create_collection_via_api() for new code.
    """
    service.merge_config_data({"collection": config})
    service.save()

    cmd = _build_collection_create_cmd(config)
    logger.info("GlobusService id=%s: running collection create: %s", service.pk, cmd)
    success, output = _exec_in_container(service.node_name, service.container_id, cmd)

    if success:
        collection_id = _extract_uuid(output)
        if collection_id:
            existing = service.get_config_data()
            existing.setdefault("collection", {})["id"] = collection_id
            service.set_config_data(existing)
            service.save()
        _transition(service, GlobusService.Status.COLLECTIONS_CONFIGURED)
    else:
        _transition(service, GlobusService.Status.ERROR, error_msg=output)

    return success, output


def run_arbitrary_exec(service: GlobusService, cmd: str) -> Tuple[bool, str]:
    """
    Execute an arbitrary command inside the service's container.
    Does not change service status.
    """
    logger.info("GlobusService id=%s: arbitrary exec: %s", service.pk, cmd)
    return _exec_in_container(service.node_name, service.container_id, cmd)


# ---------------------------------------------------------------------------
# Output parsing helpers
# ---------------------------------------------------------------------------

def _extract_endpoint_id(output: str) -> Optional[str]:
    """
    Attempt to extract a Globus endpoint UUID from GCS CLI output.
    GCS typically prints: "Created endpoint <UUID>" or similar.
    """
    import re
    # Match a UUID pattern (8-4-4-4-12 hex)
    pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    matches = re.findall(pattern, output, re.IGNORECASE)
    return matches[0] if matches else None


def _extract_uuid(output: str) -> Optional[str]:
    """Extract the first UUID from a string (generic helper)."""
    return _extract_endpoint_id(output)
