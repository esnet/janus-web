"""
gcs_service.py — Wrapper around globus-sdk v4 for GCS v5 operations.

Handles:
  - OAuth2 authorization URL generation (NativeAppAuthClient flow)
  - Authorization code exchange for tokens
  - Token refresh
  - GCSClient factory (v4: takes gcs_address, not endpoint_id)
  - High-level GCS endpoint / storage-gateway / collection operations

globus-sdk v4 API notes:
  - GCSClient(gcs_address=<fqdn_or_url>, authorizer=...)
  - StorageGatewayDocument(connector_id=<uuid>, display_name=..., ...)
  - MappedCollectionDocument(collection_base_path=..., display_name=..., ...)
  - EndpointDocument(display_name=..., organization=..., ...)
  - AuthClient(authorizer=...)
  - TransferClient(authorizer=...)
"""

import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)


class HostOverrideAdapter(HTTPAdapter):
    """
    A requests HTTPAdapter that redirects TCP connections for a specific hostname
    to a fixed IP address, while preserving the TLS SNI and Host header.

    This is used in local/NAT environments where the GCS Manager's public FQDN
    (e.g. ``062b47.6fbd.gaccess.io``) is not DNS-resolvable from the janus-web
    host, but the GCS Manager container is reachable at a local IP (e.g. 127.0.0.1).

    The GCS Manager's Apache vhost matches on the Host header and TLS SNI, so the
    FQDN must appear in both — only the TCP destination IP is overridden.

    urllib3 sets the Host header from the URL hostname, so we rewrite the URL to
    use the local IP but pass ``server_hostname`` to urllib3 so that:
      - TLS SNI uses the public FQDN (cert validation target)
      - The Host header is explicitly set to the public FQDN

    Usage::

        adapter = HostOverrideAdapter(hostname="062b47.6fbd.gaccess.io", target_ip="127.0.0.1")
        session.mount("https://062b47.6fbd.gaccess.io", adapter)
    """

    def __init__(self, hostname: str, target_ip: str, **kwargs):
        self._hostname = hostname
        self._target_ip = target_ip
        super().__init__(**kwargs)

    def send(self, request, **kwargs):
        # Rewrite the URL so TCP connects to target_ip.
        parsed = urllib.parse.urlparse(request.url)
        if parsed.hostname == self._hostname:
            port = parsed.port
            new_netloc = self._target_ip if port is None else f"{self._target_ip}:{port}"
            request.url = urllib.parse.urlunparse(parsed._replace(netloc=new_netloc))
            # Explicitly set Host header to the public FQDN.
            # urllib3 will use the URL hostname for Host, so we override it here.
            # This must be set BEFORE super().send() is called.
            request.headers["Host"] = self._hostname
        # Always disable TLS verification when using a local IP override.
        kwargs["verify"] = False
        # Pass server_hostname so urllib3 uses the public FQDN for TLS SNI,
        # even though the TCP connection goes to the local IP.
        kwargs.setdefault("proxies", {})
        return super().send(request, **kwargs)

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        # Override to inject server_hostname for correct TLS SNI.
        parsed = urllib.parse.urlparse(request.url)
        conn = super().get_connection_with_tls_context(request, verify, proxies=proxies, cert=cert)
        # Set server_hostname on the connection so TLS SNI uses the public FQDN.
        if hasattr(conn, 'conn_kw'):
            conn.conn_kw['server_hostname'] = self._hostname
        return conn

# ---------------------------------------------------------------------------
# Globus OAuth2 scopes required for GCS management
# ---------------------------------------------------------------------------
GCS_SCOPES = [
    "openid",
    "profile",
    "email",
    "urn:globus:auth:scope:transfer.api.globus.org:all",
]

GCS_SCOPE_STRING = " ".join(GCS_SCOPES)


def _get_native_client(client_id: str):
    """Return a globus_sdk.NativeAppAuthClient for the given client_id."""
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError(
            "globus-sdk is not installed. Add 'globus-sdk>=3.40.0' to requirements.txt."
        ) from exc
    return globus_sdk.NativeAppAuthClient(client_id)


# Globus out-of-band redirect URI — shows the auth code directly on the Globus page
# so the user can copy and paste it. No redirect to our server needed.
GLOBUS_OOB_REDIRECT_URI = "https://auth.globus.org/v2/web/auth-code"


def get_auth_url(client_id: str, redirect_uri: str, state: str) -> tuple:
    """
    Generate a Globus Auth authorization URL using the out-of-band (OOB) flow.

    Uses redirect_uri=https://auth.globus.org/v2/web/auth-code so that after
    authentication, Globus displays the authorization code directly on the page
    for the user to copy and paste — no redirect to our server is needed.

    Returns:
        (auth_url, verifier) — the authorization URL and the PKCE verifier string.
        The verifier MUST be stored in the Django session and passed back to
        exchange_code_for_tokens() to complete the PKCE flow.
    """
    client = _get_native_client(client_id)
    # Use the OOB redirect URI so Globus shows the code on-screen
    client.oauth2_start_flow(
        redirect_uri=GLOBUS_OOB_REDIRECT_URI,
        requested_scopes=GCS_SCOPE_STRING,
        state=state,
        refresh_tokens=True,
    )
    auth_url = client.oauth2_get_authorize_url()

    # Extract the verifier — globus-sdk recomputes the challenge from it
    verifier = None
    flow = getattr(client, 'current_oauth2_flow_manager', None)
    if flow:
        verifier = getattr(flow, 'verifier', None)

    return auth_url, verifier


def exchange_code_for_tokens(client_id: str, redirect_uri: str, code: str, pkce_data: dict = None) -> dict:
    """
    Exchange an authorization code for Globus tokens.

    Args:
        client_id:    Globus application client ID.
        redirect_uri: The redirect URI used in get_auth_url().
        code:         The authorization code from Globus.
        pkce_data:    Dict with 'verifier' key from get_auth_url().
                      The verifier is passed directly to oauth2_start_flow() so
                      globus-sdk recomputes the correct challenge from it.

    Returns a dict with keys:
        access_token, refresh_token, expiry (ISO-8601 str), scopes, all_tokens
    """
    client = _get_native_client(client_id)
    # Pass the saved verifier directly — globus-sdk will recompute the challenge
    # from it using _make_native_app_challenge(verifier), ensuring the exchange
    # sends the correct code_verifier that matches the challenge in the auth URL.
    verifier = pkce_data.get('verifier') if pkce_data else None
    logger.info(
        "exchange_code_for_tokens: verifier length=%s, verifier[:10]=%s",
        len(verifier) if verifier else 0,
        (verifier[:10] + '...') if verifier else 'None',
    )
    # IMPORTANT: redirect_uri in the exchange must match the one used in get_auth_url()
    # We always use the OOB redirect URI for the manual code paste flow.
    client.oauth2_start_flow(
        redirect_uri=GLOBUS_OOB_REDIRECT_URI,
        requested_scopes=GCS_SCOPE_STRING,
        refresh_tokens=True,
        verifier=verifier,
    )
    token_response = client.oauth2_exchange_code_for_tokens(code)
    return _parse_token_response(token_response)


def refresh_tokens(client_id: str, refresh_token: str) -> dict:
    """
    Use a refresh token to obtain a new access token.

    Returns the same dict shape as exchange_code_for_tokens.
    """
    client = _get_native_client(client_id)
    token_response = client.oauth2_refresh_token(refresh_token)
    return _parse_token_response(token_response)


def _parse_token_response(token_response) -> dict:
    """
    Normalize a globus_sdk OAuthTokenResponse into a plain dict.
    Prefers transfer.api.globus.org tokens; falls back to first available.
    """
    by_rs = token_response.by_resource_server

    rs_key = "transfer.api.globus.org"
    if rs_key not in by_rs:
        rs_key = next(iter(by_rs), None)

    if rs_key is None:
        raise ValueError("No tokens returned from Globus Auth")

    entry = by_rs[rs_key]
    expires_in = entry.get("expires_in", 0)
    expiry_dt = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)

    return {
        "access_token": entry.get("access_token"),
        "refresh_token": entry.get("refresh_token"),
        "expiry": expiry_dt.isoformat(),
        "scopes": entry.get("scope", ""),
        "resource_server": rs_key,
        "all_tokens": {
            rs: {
                "access_token": v.get("access_token"),
                "refresh_token": v.get("refresh_token"),
                "scope": v.get("scope", ""),
            }
            for rs, v in by_rs.items()
        },
    }


def get_transfer_client(access_token: str):
    """
    Return a globus_sdk.TransferClient authenticated with the given access token.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    authorizer = globus_sdk.AccessTokenAuthorizer(access_token)
    return globus_sdk.TransferClient(authorizer=authorizer)


def derive_gcs_address(endpoint_id: str) -> str:
    """
    Derive the GCS Manager FQDN from an endpoint UUID.

    GCS v5 endpoints are reachable at <endpoint_id>.data.globus.org.

    Args:
        endpoint_id: The Globus endpoint UUID (e.g. "abc123...").

    Returns:
        FQDN string, e.g. "abc123....data.globus.org".
    """
    return f"{endpoint_id}.data.globus.org"


def get_gcs_manager_hostname(local_ip: str = "127.0.0.1", port: int = 443) -> Optional[str]:
    """
    Discover the GCS Manager's actual hostname by reading the CN from its TLS certificate.

    The GCS Manager's Apache vhost is configured for its own hostname (e.g.
    ``062b47.6fbd.gaccess.io``), not for the Globus Transfer alias
    (``<uuid>.data.globus.org``).  Requests must use the actual hostname as both
    the URL host and the Host header for Apache to route them correctly.

    This function connects to the GCS Manager at ``local_ip:port``, reads the TLS
    certificate, and returns the CN field.  Called once after node container launch
    so the hostname can be stored in config_data for subsequent API calls.

    Args:
        local_ip: IP address of the GCS Manager (default: "127.0.0.1").
        port:     HTTPS port (default: 443).

    Returns:
        Hostname string (e.g. "062b47.6fbd.gaccess.io"), or None on failure.
    """
    import ssl
    import socket

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((local_ip, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=local_ip) as ssock:
                cert = ssock.getpeercert(binary_form=True)

        # Parse the DER-encoded cert to extract the CN
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        parsed = x509.load_der_x509_certificate(cert, default_backend())
        cn = parsed.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        if cn:
            hostname = cn[0].value
            logger.info("Discovered GCS Manager hostname from TLS cert: %s", hostname)
            return hostname
    except ImportError:
        # cryptography package not available — fall back to ssl.getpeercert dict
        try:
            ctx2 = ssl.create_default_context()
            ctx2.check_hostname = False
            ctx2.verify_mode = ssl.CERT_NONE
            with socket.create_connection((local_ip, port), timeout=5) as sock:
                with ctx2.wrap_socket(sock, server_hostname=local_ip) as ssock:
                    cert_dict = ssock.getpeercert()
            # cert_dict subject is a tuple of tuples: ((('commonName', 'hostname'),),)
            for rdns in cert_dict.get("subject", []):
                for attr, value in rdns:
                    if attr == "commonName":
                        logger.info("Discovered GCS Manager hostname from TLS cert: %s", value)
                        return value
        except Exception as exc:
            logger.warning("Could not read GCS Manager TLS cert (fallback): %s", exc)
    except Exception as exc:
        logger.warning("Could not discover GCS Manager hostname from TLS cert: %s", exc)
    return None


def get_gcs_client(gcs_address: str, access_token: str):
    """
    Return a globus_sdk.GCSClient for the given GCS endpoint.

    Args:
        gcs_address:  The FQDN or base URL of the GCS endpoint
                      (e.g. "abc123.data.globus.org" or "https://abc123.data.globus.org").
        access_token: A valid Globus access token with GCS management scope.

    Returns:
        A globus_sdk.GCSClient instance.

    Note (v4 API change):
        globus-sdk v4 uses `gcs_address` (FQDN/URL), not `endpoint_id`.
        The GCS endpoint's FQDN is available from the endpoint info after setup.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    authorizer = globus_sdk.AccessTokenAuthorizer(access_token)
    return globus_sdk.GCSClient(gcs_address=gcs_address, authorizer=authorizer)

def get_gcs_client_service_account(
    gcs_address: str,
    endpoint_id: str,
    verify_tls: bool = True,
    local_address: str = "",
):
    """
    Return a globus_sdk.GCSClient authenticated via the service account
    (ConfidentialAppAuthClient + ClientCredentialsAuthorizer).

    This is the preferred path for programmatic gateway/collection management
    without user interaction.  The service account credentials are read from
    Django settings (GLOBUS_SERVICE_CLIENT_ID / GLOBUS_SERVICE_CLIENT_SECRET).

    The required scope is:
        urn:globus:auth:scope:<endpoint_id>:manage_collections

    Args:
        gcs_address:   Public FQDN of the GCS endpoint (e.g. "<uuid>.data.globus.org"
                       or the GCS Manager hostname like "062b47.6fbd.gaccess.io").
                       Always use the public FQDN — it becomes the URL and Host header.
        endpoint_id:   The Globus endpoint UUID — used to build the manage_collections scope.
        verify_tls:    Whether to verify the TLS certificate.  Ignored when local_address
                       is set (TLS verification is always disabled for local overrides).
        local_address: If set (e.g. "127.0.0.1"), TCP connections are made to this IP
                       instead of resolving gcs_address via DNS, while the Host header
                       retains the public FQDN so the GCS Manager vhost routes correctly.
                       Used in local/NAT environments where the public FQDN is not routable.

    Returns:
        A globus_sdk.GCSClient instance authorised as the service account.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    from django.conf import settings
    from globus_sdk.transport import RequestsTransport

    client_id = getattr(settings, "GLOBUS_SERVICE_CLIENT_ID", None)
    client_secret = getattr(settings, "GLOBUS_SERVICE_CLIENT_SECRET", None)
    if not client_id or not client_secret:
        raise RuntimeError(
            "GLOBUS_SERVICE_CLIENT_ID and GLOBUS_SERVICE_CLIENT_SECRET must be set in settings."
        )

    # Build the manage_collections scope for this specific endpoint
    manage_collections_scope = f"urn:globus:auth:scope:{endpoint_id}:manage_collections"

    confidential_client = globus_sdk.ConfidentialAppAuthClient(client_id, client_secret)
    authorizer = globus_sdk.ClientCredentialsAuthorizer(
        confidential_client, scopes=manage_collections_scope
    )

    if local_address:
        # Local/NAT mode: TCP connects to local_address but Host header stays as the
        # public FQDN so the GCS Manager's Apache vhost routes requests correctly.
        # TLS verification is disabled because the cert is for the public hostname.
        fqdn = gcs_address.replace("https://", "").split("/")[0]
        transport = RequestsTransport(verify_ssl=False)
        transport.session.mount(
            f"https://{fqdn}",
            HostOverrideAdapter(hostname=fqdn, target_ip=local_address),
        )
    elif not verify_tls:
        transport = RequestsTransport(verify_ssl=False)
    else:
        transport = None

    return globus_sdk.GCSClient(
        gcs_address=gcs_address,
        authorizer=authorizer,
        transport=transport,
    )


def get_endpoint_info(client) -> dict:
    """
    Retrieve endpoint details from the GCS API.

    Args:
        client: A globus_sdk.GCSClient instance.

    Returns:
        Dict of endpoint properties.
    """
    try:
        response = client.get_endpoint()
        return response.data or {}
    except Exception as exc:
        logger.error("Failed to get endpoint info: %s", exc)
        raise


def update_endpoint(client, data: dict) -> dict:
    """
    Update endpoint properties via the GCS API.

    Args:
        client: A globus_sdk.GCSClient instance.
        data:   Dict of fields to update.
                Valid keys: display_name, organization, contact_email, contact_info,
                            description, department, info_link, network_use.

    Returns:
        Updated endpoint dict.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    # Filter to only EndpointDocument-accepted fields
    allowed = {
        "display_name", "organization", "contact_email", "contact_info",
        "description", "department", "info_link", "network_use",
    }
    filtered = {k: v for k, v in data.items() if k in allowed and v}
    try:
        doc = globus_sdk.EndpointDocument(**filtered)
        response = client.update_endpoint(doc)
        return response.data or {}
    except Exception as exc:
        logger.error("Failed to update endpoint: %s", exc)
        raise


def list_storage_gateways(client) -> list:
    """
    List all storage gateways on the GCS endpoint.

    Args:
        client: A globus_sdk.GCSClient instance.

    Returns:
        List of storage gateway dicts.
    """
    try:
        response = client.get_storage_gateway_list()
        return list(response)
    except Exception as exc:
        logger.error("Failed to list storage gateways: %s", exc)
        raise


def list_collections(client) -> list:
    """
    List all collections on the GCS endpoint.

    Args:
        client: A globus_sdk.GCSClient instance.

    Returns:
        List of collection dicts.
    """
    try:
        response = client.get_collection_list()
        return list(response)
    except Exception as exc:
        logger.error("Failed to list collections: %s", exc)
        raise


def create_storage_gateway(client, data: dict) -> dict:
    """
    Create a storage gateway on the GCS endpoint.

    Args:
        client: A globus_sdk.GCSClient instance.
        data:   Dict with storage gateway configuration.
                Required: connector_id (UUID of the connector type),
                          display_name
                Optional:
                  allowed_domains  – list of Globus Auth domain strings
                  users_deny       – list of local usernames to deny
                  restrict_paths   – dict with keys "none", "read", "read_write"
                                     (each a list of path strings); passed as
                                     additional_fields on StorageGatewayDocument
                  high_assurance, policies, root, require_mfa

    Returns:
        Created storage gateway dict (includes 'id').

    Note:
        connector_id is the UUID for the connector type (e.g. POSIX connector UUID).
        Use globus_sdk.ConnectorTable to look up connector UUIDs by name.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    # Fields accepted directly by StorageGatewayDocument.__init__()
    direct_fields = {
        "connector_id", "display_name", "allowed_domains", "high_assurance",
        "identity_mappings", "policies", "root", "require_mfa",
        "users_allow", "users_deny",
    }
    filtered = {k: v for k, v in data.items() if k in direct_fields and v is not None}

    # restrict_paths is not a named parameter on StorageGatewayDocument — pass
    # it via additional_fields so it is included verbatim in the JSON body.
    additional: dict = {}
    restrict_paths = data.get("restrict_paths")
    if restrict_paths:
        # Ensure the DATA_TYPE key is present
        if "DATA_TYPE" not in restrict_paths:
            restrict_paths = {"DATA_TYPE": "path_restrictions#1.0.0", **restrict_paths}
        additional["restrict_paths"] = restrict_paths

    try:
        doc = globus_sdk.StorageGatewayDocument(
            **filtered,
            additional_fields=additional if additional else None,
        )
        response = client.create_storage_gateway(doc)
        return response.data or {}
    except globus_sdk.GCSAPIError as exc:
        # 409 conflict means a gateway with this display_name already exists.
        # The response detail contains the existing gateway UUID(s) in
        # detail.resources — reuse the first one so the wizard is idempotent.
        if exc.http_status == 409:
            try:
                resources = exc.raw_json.get("detail", {}).get("resources", [])
                if resources:
                    existing_id = resources[0]
                    logger.warning(
                        "Storage gateway with this display_name already exists "
                        "(id=%s); reusing it.", existing_id,
                    )
                    return {"id": existing_id, "_reused": True}
            except Exception:
                pass
        logger.error(
            "Failed to create storage gateway: %r (type=%s)",
            exc, type(exc).__name__,
            exc_info=True,
        )
        raise
    except Exception as exc:
        logger.error(
            "Failed to create storage gateway: %r (type=%s)",
            exc, type(exc).__name__,
            exc_info=True,
        )
        raise


def update_storage_gateway(client, gateway_id: str, data: dict) -> dict:
    """
    Update an existing storage gateway.

    Args:
        client:     A globus_sdk.GCSClient instance.
        gateway_id: UUID of the storage gateway to update.
        data:       Dict of fields to update.

    Returns:
        Updated storage gateway dict.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    allowed = {
        "display_name", "allowed_domains", "high_assurance",
        "identity_mappings", "policies", "root", "require_mfa",
    }
    filtered = {k: v for k, v in data.items() if k in allowed and v is not None}
    try:
        doc = globus_sdk.StorageGatewayDocument(**filtered)
        response = client.update_storage_gateway(gateway_id, doc)
        return response.data or {}
    except Exception as exc:
        logger.error("Failed to update storage gateway %s: %s", gateway_id, exc)
        raise


def delete_storage_gateway(client, gateway_id: str) -> None:
    """
    Delete a storage gateway.

    Args:
        client:     A globus_sdk.GCSClient instance.
        gateway_id: UUID of the storage gateway to delete.
    """
    try:
        client.delete_storage_gateway(gateway_id)
    except Exception as exc:
        logger.error("Failed to delete storage gateway %s: %s", gateway_id, exc)
        raise


def create_collection(client, data: dict) -> dict:
    """
    Create a mapped collection on the GCS endpoint.

    Args:
        client: A globus_sdk.GCSClient instance.
        data:   Dict with collection configuration.
                Required: collection_base_path, display_name
                Optional: contact_email, description, department, etc.

    Returns:
        Created collection dict (includes 'id').
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    allowed = {
        "collection_base_path", "display_name", "contact_email", "contact_info",
        "default_directory", "department", "description", "identity_id",
        "storage_gateway_id", "public",
        # Gap 1: organization was missing
        "organization",
        # Gap 2: keywords must be a list (assembled in services.py before reaching here)
        "keywords",
        # Gap 3: sharing path restrictions dict (assembled in services.py)
        "sharing_restrict_paths",
        # Gap 4: anonymous-write and guest-collection flags
        "disable_anonymous_writes", "allow_guest_collections",
    }
    filtered = {k: v for k, v in data.items() if k in allowed and v is not None}
    try:
        doc = globus_sdk.MappedCollectionDocument(**filtered)
        response = client.create_collection(doc)
        return response.data or {}
    except Exception as exc:
        logger.error("Failed to create collection: %s", exc)
        raise


def update_collection(client, collection_id: str, data: dict) -> dict:
    """
    Update an existing mapped collection.

    Args:
        client:        A globus_sdk.GCSClient instance.
        collection_id: UUID of the collection to update.
        data:          Dict of fields to update.

    Returns:
        Updated collection dict.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    allowed = {
        "display_name", "contact_email", "contact_info", "default_directory",
        "department", "description", "delete_protected",
    }
    filtered = {k: v for k, v in data.items() if k in allowed and v is not None}
    try:
        doc = globus_sdk.MappedCollectionDocument(**filtered)
        response = client.update_collection(collection_id, doc)
        return response.data or {}
    except Exception as exc:
        logger.error("Failed to update collection %s: %s", collection_id, exc)
        raise


def delete_collection(client, collection_id: str) -> None:
    """
    Delete a collection, first disabling delete_protected if set.

    GCS collections have delete_protected=True by default.  This function
    first patches the collection to set delete_protected=False, then deletes it.

    Args:
        client:        A globus_sdk.GCSClient instance.
        collection_id: UUID of the collection to delete.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    try:
        # Disable delete protection before deleting
        unprotect_doc = globus_sdk.MappedCollectionDocument(delete_protected=False)
        client.update_collection(collection_id, unprotect_doc)
        client.delete_collection(collection_id)
    except Exception as exc:
        logger.error("Failed to delete collection %s: %s", collection_id, exc)
        raise


def create_user_credential(client, storage_gateway_id: str, identity_id: str, username: str) -> dict:
    """
    Create a user credential on a storage gateway.

    A user credential is required before a guest collection can be created.
    It maps a Globus identity to a local POSIX username on the storage gateway.

    Args:
        client:             A globus_sdk.GCSClient instance.
        storage_gateway_id: UUID of the storage gateway.
        identity_id:        Globus identity UUID of the user (or service account client ID).
        username:           Local POSIX username to map to.

    Returns:
        Created user credential dict.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    try:
        doc = globus_sdk.UserCredentialDocument(
            storage_gateway_id=storage_gateway_id,
            identity_id=identity_id,
            username=username,
        )
        response = client.create_user_credential(doc)
        return response.data or {}
    except Exception as exc:
        logger.error("Failed to create user credential: %s", exc)
        raise


def create_guest_collection(
    client,
    mapped_collection_id: str,
    base_path: str,
    display_name: str,
    **kwargs,
) -> dict:
    """
    Create a guest collection on top of a mapped collection.

    A user credential must exist on the storage gateway before calling this.

    Args:
        client:               A globus_sdk.GCSClient instance.
        mapped_collection_id: UUID of the parent mapped collection.
        base_path:            Root path within the mapped collection.
        display_name:         Human-readable name for the guest collection.
        **kwargs:             Additional GuestCollectionDocument fields
                              (description, contact_email, etc.).

    Returns:
        Created guest collection dict (includes 'id').
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    try:
        doc = globus_sdk.GuestCollectionDocument(
            mapped_collection_id=mapped_collection_id,
            collection_base_path=base_path,
            display_name=display_name,
            **kwargs,
        )
        response = client.create_collection(doc)
        return response.data or {}
    except Exception as exc:
        logger.error("Failed to create guest collection: %s", exc)
        raise


def get_connector_id(connector_name: str) -> Optional[str]:
    """
    Look up the Globus connector UUID by a human-readable name.

    Uses ``globus_sdk.ConnectorTable.lookup()`` (available in v4) which
    normalises names so that "posix", "POSIX", "posix-staging" etc. all work.

    Args:
        connector_name: e.g. "posix", "s3", "google-cloud-storage"

    Returns:
        UUID string or None if not found.
    """
    try:
        import globus_sdk
    except ImportError:
        return None

    # Use ConnectorTable.lookup() — it normalises names (case-insensitive,
    # spaces/dashes/underscores treated equivalently) and returns a
    # GlobusConnectServerConnector with a .connector_id attribute.
    try:
        connector = globus_sdk.ConnectorTable.lookup(connector_name)
        if connector is not None:
            return str(connector.connector_id)
    except Exception:
        pass

    # Fallback map with correct UUIDs from ConnectorTable._connectors (SDK v4.6)
    name_map = {
        "posix":                "145812c8-decc-41f1-83cf-bb2a85a2a70b",
        "posix-staging":        "052be037-7dda-4d20-b163-3077314dc3e6",
        "s3":                   "7643e831-5f6c-4b47-a07f-8ee90f401d23",
        "google-cloud-storage": "56366b96-ac98-11e9-abac-9cb6d0d9fd63",
        "google-drive":         "976cf0cf-78c3-4aab-82d2-7c16adbcc281",
        "azure-blob":           "9436da0c-a444-11eb-af93-12704e0d6a4d",
        "blackpearl":           "7e3f3f5e-350c-4717-891a-2f451c24b0d4",
        "box":                  "7c100eae-40fe-11e9-95a3-9cb6d0d9fd63",
        "ceph":                 "1b6374b0-f6a4-4cf7-a26f-f262d9c6ca72",
        "irods":                "e47b6920-ff57-11ea-8aaa-000c297ab3c2",
        "onedrive":             "28ef55da-1f97-11eb-bdfd-12704e0d6a4d",
        "hpss":                 "fb656a17-0f69-4e59-95ff-d0a62ca7bdf5",
        "activescale":          "7251f6c8-93c9-11eb-95ba-12704e0d6a4d",
        "dropbox":              "49b00fd6-63f1-48ae-b27f-d8af4589f876",
    }
    return name_map.get(connector_name.lower())


def get_globus_identities(access_token: str, usernames: list) -> list:
    """
    Look up Globus identity records for a list of usernames/emails.

    Args:
        access_token: A valid Globus Auth access token.
        usernames:    List of Globus usernames or email addresses.

    Returns:
        List of identity dicts from the Globus Auth API.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    authorizer = globus_sdk.AccessTokenAuthorizer(access_token)
    auth_client = globus_sdk.AuthClient(authorizer=authorizer)
    try:
        response = auth_client.get_identities(usernames=usernames)
        return response.data.get("identities", [])
    except Exception as exc:
        logger.error("Failed to get Globus identities: %s", exc)
        raise


def get_globus_identity_id(username_or_email: str) -> Optional[str]:
    """
    Look up a Globus identity UUID by username or email using the service account.

    Uses ConfidentialAppAuthClient so no user token is required.

    Args:
        username_or_email: Globus username or email address.

    Returns:
        Identity UUID string, or None if not found.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    from django.conf import settings

    client_id = getattr(settings, "GLOBUS_SERVICE_CLIENT_ID", None)
    client_secret = getattr(settings, "GLOBUS_SERVICE_CLIENT_SECRET", None)
    if not client_id or not client_secret:
        raise RuntimeError("GLOBUS_SERVICE_CLIENT_ID/SECRET not configured.")

    confidential_client = globus_sdk.ConfidentialAppAuthClient(client_id, client_secret)
    try:
        response = confidential_client.get_identities(usernames=[username_or_email])
        identities = response.data.get("identities", [])
        return identities[0]["id"] if identities else None
    except Exception as exc:
        logger.error("Failed to get Globus identity for %s: %s", username_or_email, exc)
        raise


def set_endpoint_owner_via_api(
    gcs_address: str,
    identity_id: str,
    access_token: str,
    verify_tls: bool = True,
    local_address: str = "",
) -> dict:
    """
    Transfer endpoint ownership to a Globus identity via the GCS Manager REST API.

    The GCS SDK has no method for this — it must be done via raw HTTP PUT to
    https://<gcs_address>/api/endpoint/owner.

    Args:
        gcs_address:   Public FQDN of the GCS endpoint (e.g. "<uuid>.data.globus.org").
                       Always use the public FQDN — it is used as the URL and Host header.
        identity_id:   Globus identity UUID to set as owner.
        access_token:  Bearer token with manage_collections scope.
        verify_tls:    Whether to verify the TLS certificate.  Ignored when local_address
                       is set (TLS verification is always disabled for local overrides).
        local_address: If set (e.g. "127.0.0.1"), TCP connections are made to this IP
                       instead of resolving gcs_address via DNS.  The Host header retains
                       the public FQDN so the GCS Manager vhost routes correctly.

    Returns:
        Response JSON dict.
    """
    url = f"https://{gcs_address}/api/endpoint/owner"
    payload = {
        "DATA_TYPE": "endpoint_owner#1.0.0",
        "identity_id": identity_id,
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        if local_address:
            # Use requests with HostOverrideAdapter so TCP goes to local_address
            # but the Host header stays as the public FQDN.
            session = requests.Session()
            session.mount(
                f"https://{gcs_address}",
                HostOverrideAdapter(hostname=gcs_address, target_ip=local_address),
            )
            resp = session.put(url, headers=headers, json=payload, timeout=30.0, verify=False)
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        else:
            import httpx
            resp = httpx.put(
                url,
                headers=headers,
                json=payload,
                timeout=30.0,
                verify=verify_tls,
            )
            resp.raise_for_status()
            return resp.json() if resp.content else {}
    except Exception as exc:
        logger.error("Failed to set endpoint owner to %s: %s", identity_id, exc)
        raise


def create_role(client, collection_id: str, identity_id: str, role: str = "administrator") -> dict:
    """
    Create a role on a GCS endpoint or collection.

    Used to grant a Globus identity (e.g. the human user) administrator access
    after the service account has taken ownership of the endpoint.

    Args:
        client:        A globus_sdk.GCSClient instance.
        collection_id: UUID of the endpoint or collection to grant the role on.
        identity_id:   Globus identity UUID to grant the role to.
        role:          Role name — "administrator", "access_manager", "activity_manager",
                       "activity_monitor", or "owner".

    Returns:
        Created role dict.
    """
    try:
        import globus_sdk
    except ImportError as exc:
        raise RuntimeError("globus-sdk is not installed.") from exc

    try:
        doc = globus_sdk.GCSRoleDocument(
            collection=collection_id,
            principal=f"urn:globus:auth:identity:{identity_id}",
            role=role,
        )
        response = client.create_role(doc)
        return response.data or {}
    except Exception as exc:
        logger.error("Failed to create role %s for %s on %s: %s", role, identity_id, collection_id, exc)
        raise
