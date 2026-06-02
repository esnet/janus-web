"""
views.py — REST API views for the Globus Service handler.

All endpoints require an authenticated Django session.
URL prefix: /janus/services/  (wired in webapp/urls.py via globus_service.urls)

Key workflow notes from real-world GCS usage:
  1. Endpoint setup is INTERACTIVE — use the WebSocket (ws/gcs-interactive/<id>/)
     to run `globus-connect-server endpoint setup ...` and paste the auth code.
  2. After endpoint setup, call /endpoint/deployment-key/ to collect the key JSON.
  3. The node container is launched with DEPLOYMENT_KEY env var (not via CLI inside
     the endpoint container).
  4. Before storage-gateway creation, run `globus-connect-server login <endpoint-id>`
     interactively via WebSocket, then optionally `endpoint set-owner <service-acct>`.
"""

import json
import logging

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

from . import services
from .models import GlobusService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_auth(request):
    """Return a 401 JsonResponse if the user is not authenticated, else None."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Unauthorized"}, status=401)
    return None


def _parse_json_body(request):
    """Parse JSON body; return (data, None) or (None, error_response)."""
    try:
        data = json.loads(request.body)
        return data, None
    except (json.JSONDecodeError, ValueError):
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)


# ---------------------------------------------------------------------------
# Template views (mount points for Vue components)
# ---------------------------------------------------------------------------

def services_list_view(request):
    """Render the Services dashboard page (mounts ServicesDashboard Vue component)."""
    if not request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect("/")
    user = User.objects.get(username=request.user)
    return render(request, "services.html", {
        "login": True,
        "user": user.username,
        "is_admin": user.is_staff,
    })


def globus_wizard_view(request):
    """Render the Globus Service wizard page (mounts GlobusServiceWizard Vue component)."""
    if not request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect("/")
    user = User.objects.get(username=request.user)
    return render(request, "globus_service.html", {
        "login": True,
        "user": user.username,
        "is_admin": user.is_staff,
    })


# ---------------------------------------------------------------------------
# Service list / create / detail / delete
# ---------------------------------------------------------------------------

def list_services_api(request):
    """
    GET /janus/api/services/globus/
    Returns all GlobusService records for the authenticated user.
    """
    err = _require_auth(request)
    if err:
        return err

    service_list = services.list_services(request.user)
    return JsonResponse({"services": service_list})


def create_service_api(request):
    """
    POST /janus/api/services/globus/create/
    Body: {session_id, node_name, container_id, display_name}
    Creates a new GlobusService in PENDING state.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data, err = _parse_json_body(request)
    if err:
        return err

    session_id = data.get("session_id")
    node_name = data.get("node_name", "")
    container_id = data.get("container_id", "")
    display_name = data.get("display_name", "")

    if not session_id:
        return JsonResponse({"error": "session_id is required"}, status=400)

    service = services.create_service(
        user=request.user,
        session_id=int(session_id),
        node_name=node_name,
        container_id=container_id,
        display_name=display_name,
    )
    return JsonResponse({"service": service.to_dict()}, status=201)


def get_service_api(request, service_id):
    """
    GET /janus/api/services/globus/<service_id>/
    Returns details of a single GlobusService.
    """
    err = _require_auth(request)
    if err:
        return err

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    return JsonResponse({"service": service.to_dict()})


def delete_service_api(request, service_id):
    """
    DELETE /janus/api/services/globus/<service_id>/delete/
    Deletes a GlobusService record.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    deleted = services.delete_service(service_id, request.user)
    if not deleted:
        return JsonResponse({"error": "Service not found"}, status=404)

    return JsonResponse({"status": "deleted"})


# ---------------------------------------------------------------------------
# Globus Auth flow
# ---------------------------------------------------------------------------

def get_auth_url_api(request):
    """
    GET /janus/services/api/globus/auth/url/
    Returns a Globus Auth authorization URL and stores the state token and PKCE
    verifier in the Django session for use during the callback.
    """
    err = _require_auth(request)
    if err:
        return err

    # Use the OOB redirect URI — Globus shows the code on-screen for manual paste
    # No redirect to our server needed; the user copies and pastes the code.
    from globus_service.gcs_service import GLOBUS_OOB_REDIRECT_URI

    try:
        auth_url, state, pkce_data = services.build_auth_url(GLOBUS_OOB_REDIRECT_URI)
    except RuntimeError as exc:
        logger.error("Failed to build Globus auth URL: %s", exc)
        return JsonResponse({"error": str(exc)}, status=500)

    # Store PKCE data in Django session for use during code exchange
    if pkce_data:
        request.session["globus_oauth_pkce"] = pkce_data
    request.session.modified = True

    return JsonResponse({"auth_url": auth_url, "state": state})


def auth_callback_api(request):
    """
    POST /janus/services/api/globus/auth/callback/
    Body: {code}
    Exchanges the authorization code (pasted by user from Globus OOB page) for tokens.
    Uses the PKCE verifier stored in the session during get_auth_url_api().
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data, err = _parse_json_body(request)
    if err:
        return err

    code = data.get("code")

    if not code:
        return JsonResponse({"error": "Authorization code is required"}, status=400)

    # Retrieve the PKCE data stored during get_auth_url_api()
    pkce_data = request.session.get("globus_oauth_pkce")

    # Use the OOB redirect URI (must match what was used in get_auth_url_api)
    from globus_service.gcs_service import GLOBUS_OOB_REDIRECT_URI

    try:
        token_data = services.complete_auth(
            request.user, code, GLOBUS_OOB_REDIRECT_URI, pkce_data=pkce_data
        )
    except Exception as exc:
        logger.error("Globus auth callback failed for user %s: %s", request.user.username, exc)
        return JsonResponse({"error": f"Token exchange failed: {exc}"}, status=500)

    # Clean up session state
    request.session.pop("globus_oauth_state", None)
    request.session.pop("globus_oauth_redirect_uri", None)
    request.session.pop("globus_oauth_pkce", None)

    return JsonResponse({
        "status": "authenticated",
        "scopes": token_data.get("scopes", ""),
        "expiry": token_data.get("expiry", ""),
    })


def auth_status_api(request):
    """
    GET /janus/api/services/globus/auth/status/
    Returns whether the user has valid Globus tokens.
    """
    err = _require_auth(request)
    if err:
        return err

    has_tokens = services.has_valid_tokens(request.user)
    return JsonResponse({"authenticated": has_tokens})


def auth_logout_api(request):
    """
    POST /janus/api/services/globus/auth/logout/
    Removes stored Globus tokens for the user.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    services.delete_tokens(request.user)
    return JsonResponse({"status": "logged_out"})


# ---------------------------------------------------------------------------
# GCS wizard step endpoints
# ---------------------------------------------------------------------------

def setup_endpoint_api(request, service_id):
    """
    POST /janus/api/services/globus/<service_id>/endpoint/setup/
    Body: {display_name, organization, contact_email, owner}
    Runs `globus-connect-server endpoint setup` inside the container.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    data, err = _parse_json_body(request)
    if err:
        return err

    # Validate required fields
    required = ["display_name", "organization", "contact_email"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return JsonResponse(
            {"error": f"Missing required fields: {', '.join(missing)}"}, status=400
        )

    success, output = services.run_endpoint_setup(service, data)
    return JsonResponse({
        "success": success,
        "output": output,
        "service": service.to_dict(),
    }, status=200 if success else 400)


def set_endpoint_id_api(request, service_id):
    """
    POST /janus/services/api/globus/<service_id>/endpoint/set-id/
    Body: {endpoint_id: "..."}
    Manually set the Globus endpoint ID on the service (when auto-extraction fails).
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    data, err = _parse_json_body(request)
    if err:
        return err

    endpoint_id = (data.get("endpoint_id") or "").strip()
    if not endpoint_id:
        return JsonResponse({"error": "endpoint_id is required"}, status=400)

    service.globus_endpoint_id = endpoint_id
    service.save(update_fields=["globus_endpoint_id"])
    logger.info("GlobusService id=%s: endpoint_id manually set to %s", service.pk, endpoint_id)
    return JsonResponse({"success": True, "service": service.to_dict()})


def setup_node_api(request, service_id):
    """
    POST /janus/services/api/globus/<service_id>/node/setup/
    Body: {node_name (optional), node_setup_args (optional)}

    Launches a new Janus session with the GCS image and DEPLOYMENT_KEY env var set.
    The container's /entrypoint.sh reads DEPLOYMENT_KEY, runs node setup, and starts
    all GCS services (GCS Manager, Apache, GridFTP).

    The deployment key must have been collected via /endpoint/deployment-key/ first.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    data, parse_err = _parse_json_body(request)
    if parse_err:
        data = {}

    # Use the node_name from the request or fall back to the service's current node
    node_name = data.get("node_name", service.node_name) or "benki"
    node_setup_args = data.get("node_setup_args", "")

    success, result = services.launch_node_container(service, node_name, node_setup_args)

    if success:
        # The node container uses host networking, so the GCS Manager is reachable
        # at 127.0.0.1 from the Django server. Store this as gcs_local_address so
        # service account REST API calls work in local/NAT environments where the
        # public domain (uuid.data.globus.org) is not yet reachable.
        # Use 127.0.0.1 explicitly (not "localhost") to avoid IPv6 (::1) resolution.
        local_config = {"gcs_local_address": "127.0.0.1"}

        # Discover the GCS Manager's actual hostname from its TLS cert CN.
        # The GCS Manager's Apache vhost is configured for this hostname
        # (e.g. "5870fd.27eb.gaccess.io"), not for the <uuid>.data.globus.org alias.
        # Requests must use this hostname as the URL host for Apache to route correctly.
        # Retry for up to 60s to allow the container's HTTPS server time to start.
        import time
        from . import gcs_service as gcs_mod
        manager_hostname = None
        for attempt in range(12):  # 12 × 5s = 60s max
            time.sleep(5)
            manager_hostname = gcs_mod.get_gcs_manager_hostname(local_ip="127.0.0.1", port=443)
            if manager_hostname:
                break
            logger.debug(
                "GlobusService id=%s: GCS Manager not ready yet (attempt %d/12)",
                service.pk, attempt + 1,
            )

        if manager_hostname:
            local_config["gcs_manager_hostname"] = manager_hostname
            logger.info(
                "GlobusService id=%s: discovered GCS Manager hostname: %s",
                service.pk, manager_hostname,
            )
        else:
            logger.warning(
                "GlobusService id=%s: could not discover GCS Manager hostname from TLS cert "
                "after 60s; gateway/collection creation may fail in local/NAT environments.",
                service.pk,
            )

        service.merge_config_data(local_config)
        service.save()

    return JsonResponse({
        "success": success,
        "container_id": result if success else "",
        "error": result if not success else "",
        "service": service.to_dict(),
    }, status=200 if success else 400)


def create_gateway_api(request, service_id):
    """
    POST /janus/api/services/globus/<service_id>/gateway/create/
    Body: {connector, display_name, allowed_domains (optional list)}

    Creates a storage gateway via the GCS REST API using the service account
    (ConfidentialAppAuthClient + ClientCredentialsAuthorizer).
    No interactive GCS login is required.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    data, err = _parse_json_body(request)
    if err:
        return err

    required = ["connector", "display_name"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return JsonResponse(
            {"error": f"Missing required fields: {', '.join(missing)}"}, status=400
        )

    success, output = services.create_gateway_via_api(service, data)
    return JsonResponse({
        "success": success,
        "gateway_id": output if success else "",
        "error": output if not success else "",
        "service": service.to_dict(),
    }, status=200 if success else 400)


def list_gateways_api(request, service_id):
    """
    GET /janus/api/services/globus/<service_id>/gateway/list/
    Lists all storage gateways on the endpoint via the GCS REST API.
    """
    err = _require_auth(request)
    if err:
        return err

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    from . import gcs_service as gcs
    cfg = service.get_config_data()
    endpoint_id = service.globus_endpoint_id
    gcs_address = cfg.get("gcs_address") or (
        gcs.derive_gcs_address(endpoint_id) if endpoint_id else None
    )
    if not gcs_address or not endpoint_id:
        return JsonResponse(
            {"error": "endpoint_id not set — complete endpoint setup first."}, status=400
        )

    try:
        client = gcs.get_gcs_client_service_account(gcs_address, endpoint_id)
        gateways = gcs.list_storage_gateways(client)
        return JsonResponse({"gateways": gateways})
    except Exception as exc:
        logger.error("list_gateways_api failed for service %s: %s", service_id, exc)
        return JsonResponse({"error": str(exc)}, status=500)


def create_collection_api(request, service_id):
    """
    POST /janus/api/services/globus/<service_id>/collection/create/
    Body: {base_path, display_name, collection_type (mapped|guest),
           storage_gateway_id (optional — falls back to config_data),
           mapped_collection_id (required for guest),
           local_username (optional, default: globus)}

    Creates a mapped or guest collection via the GCS REST API using the service account.
    For guest collections, a UserCredentialDocument is created first.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    data, err = _parse_json_body(request)
    if err:
        return err

    required = ["base_path", "display_name"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return JsonResponse(
            {"error": f"Missing required fields: {', '.join(missing)}"}, status=400
        )

    success, output = services.create_collection_via_api(service, data)
    return JsonResponse({
        "success": success,
        "collection_id": output if success else "",
        "error": output if not success else "",
        "service": service.to_dict(),
    }, status=200 if success else 400)


def list_collections_api(request, service_id):
    """
    GET /janus/api/services/globus/<service_id>/collection/list/
    Lists all collections on the endpoint via the GCS REST API.
    """
    err = _require_auth(request)
    if err:
        return err

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    from . import gcs_service as gcs
    cfg = service.get_config_data()
    endpoint_id = service.globus_endpoint_id
    gcs_address = cfg.get("gcs_address") or (
        gcs.derive_gcs_address(endpoint_id) if endpoint_id else None
    )
    if not gcs_address or not endpoint_id:
        return JsonResponse(
            {"error": "endpoint_id not set — complete endpoint setup first."}, status=400
        )

    try:
        client = gcs.get_gcs_client_service_account(gcs_address, endpoint_id)
        collections = gcs.list_collections(client)
        return JsonResponse({"collections": collections})
    except Exception as exc:
        logger.error("list_collections_api failed for service %s: %s", service_id, exc)
        return JsonResponse({"error": str(exc)}, status=500)


def exec_command_api(request, service_id):
    """
    POST /janus/services/api/globus/<service_id>/exec/
    Body: {cmd}
    Execute an arbitrary command inside the service's container.
    Returns stdout/stderr output.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    data, err = _parse_json_body(request)
    if err:
        return err

    cmd = data.get("cmd", "").strip()
    if not cmd:
        return JsonResponse({"error": "cmd is required"}, status=400)

    success, output = services.run_arbitrary_exec(service, cmd)
    return JsonResponse({
        "success": success,
        "output": output,
    }, status=200 if success else 400)


def get_endpoint_setup_cmd_api(request, service_id):
    """
    POST /janus/services/api/globus/<service_id>/endpoint/cmd/
    Body: {display_name, organization, contact_email, owner, project_id,
           always_create_project, deployment_key_path}

    Returns the `globus-connect-server endpoint setup` command string.
    The caller sends this via GCSInteractiveConsumer WebSocket since it is
    interactive (requires pasting a Globus Auth code).
    Also stores the config in service.config_data for later reference.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    data, parse_err = _parse_json_body(request)
    if parse_err:
        return parse_err

    required = ["display_name", "organization", "contact_email", "owner"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return JsonResponse(
            {"error": f"Missing required fields: {', '.join(missing)}"}, status=400
        )

    success, cmd = services.run_endpoint_setup(service, data)
    return JsonResponse({
        "success": success,
        "cmd": cmd,
        "service": service.to_dict(),
        "note": (
            "Send this command via the interactive WebSocket session "
            "(ws/gcs-interactive/<service_id>/). After the auth code is accepted, "
            "call /endpoint/deployment-key/ to collect the deployment key."
        ),
    })


def fetch_deployment_key_api(request, service_id):
    """
    POST /janus/services/api/globus/<service_id>/endpoint/deployment-key/
    Body: {deployment_key_path} (optional, default: /work/deployment-key.json)

    Retrieves the deployment-key.json written by endpoint setup from the container.
    Stores it in service.config_data["deployment_key"] for use as DEPLOYMENT_KEY
    env var when launching the node container.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    data, _ = _parse_json_body(request)
    if not data:
        data = {}

    deployment_key_path = data.get("deployment_key_path", "/work/deployment-key.json")

    # If the frontend already extracted the endpoint ID from terminal output,
    # store it on the service before fetching the key so gcs_address can be derived.
    endpoint_id_hint = data.get("endpoint_id", "").strip()
    if endpoint_id_hint and not service.globus_endpoint_id:
        service.globus_endpoint_id = endpoint_id_hint
        service.save()
        logger.info(
            "GlobusService id=%s: endpoint_id set from frontend hint: %s",
            service.pk, endpoint_id_hint,
        )

    success, output = services.fetch_deployment_key(service, deployment_key_path)

    return JsonResponse({
        "success": success,
        "deployment_key": output if success else "",
        "output": output,
        "service": service.to_dict(),
    }, status=200 if success else 400)


def get_gcs_login_cmd_api(request, service_id):
    """
    GET /janus/services/api/globus/<service_id>/node/login-cmd/

    Returns the combined ``globus-connect-server login <endpoint-id>`` (and
    optionally ``&& endpoint set-owner <identity>``) command string for Step 3.5.

    The caller sends this command via the GCSInteractiveConsumer WebSocket
    (ws/gcs-interactive/<service_id>/) because ``gcs login`` is interactive —
    it prints a Globus Auth URL and waits for the user to paste back a code.

    Running this in the **node container** populates the GCS Manager's role
    database, which is required before storage gateway and collection creation.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    try:
        cmd = services.get_gcs_login_cmd(service)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({
        "cmd": cmd,
        "service": service.to_dict(),
        "note": (
            "Send this command via the interactive WebSocket session "
            "(ws/gcs-interactive/<service_id>/).  The command is interactive: "
            "GCS will print a Globus Auth URL — open it, authenticate, then "
            "paste the code back into the terminal.  Once complete, proceed to "
            "storage gateway creation."
        ),
    })


def set_endpoint_owner_api(request, service_id):
    """
    POST /janus/services/api/globus/<service_id>/endpoint/set-owner/
    Body: {service_account_id}

    Returns the `globus-connect-server endpoint set-owner` command string.
    Send this via GCSInteractiveConsumer WebSocket after completing gcs login.
    Ownership transfer is required before storage gateway creation.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    data, parse_err = _parse_json_body(request)
    if parse_err:
        return parse_err

    service_account_id = data.get("service_account_id", "").strip()
    if not service_account_id:
        return JsonResponse({"error": "service_account_id is required"}, status=400)

    success, cmd = services.set_endpoint_owner(service, service_account_id)
    return JsonResponse({
        "success": success,
        "cmd": cmd,
        "note": (
            "Send this command via the interactive WebSocket session "
            "(ws/gcs-interactive/<service_id>/) after completing gcs login."
        ),
    })


def grant_user_admin_api(request, service_id):
    """
    POST /janus/services/api/globus/<service_id>/endpoint/grant-admin/
    Body: {identity_id} OR {username} (Globus username/email to look up)

    Grants the 'administrator' role on the endpoint to a Globus identity.
    Used after service account takes ownership so the human user retains
    management access in the Globus web UI.
    """
    err = _require_auth(request)
    if err:
        return err

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    service = services.get_service(service_id, request.user)
    if service is None:
        return JsonResponse({"error": "Service not found"}, status=404)

    data, parse_err = _parse_json_body(request)
    if parse_err:
        return parse_err

    identity_id = data.get("identity_id", "").strip()
    username = data.get("username", "").strip()

    # Look up identity UUID from username if not provided directly
    if not identity_id and username:
        try:
            from . import gcs_service as gcs
            identity_id = gcs.get_globus_identity_id(username)
            if not identity_id:
                return JsonResponse(
                    {"error": f"No Globus identity found for username: {username}"}, status=404
                )
        except Exception as exc:
            return JsonResponse({"error": f"Identity lookup failed: {exc}"}, status=500)

    if not identity_id:
        return JsonResponse({"error": "identity_id or username is required"}, status=400)

    success, message = services.grant_user_admin_role(service, identity_id)
    return JsonResponse({
        "success": success,
        "message": message,
        "identity_id": identity_id,
    }, status=200 if success else 400)
