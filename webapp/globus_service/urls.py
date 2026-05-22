from django.urls import path
from . import views

app_name = "globus_service"

urlpatterns = [
    # -----------------------------------------------------------------------
    # Template / page views
    # -----------------------------------------------------------------------
    path("", views.services_list_view, name="list"),
    path("globus/", views.globus_wizard_view, name="create"),
    # OAuth2 redirect target — Globus redirects here with ?code=...&state=...
    # The GlobusAuthPane Vue component detects the code on mount and exchanges it.
    path("globus/auth/callback/", views.globus_wizard_view, name="auth_callback_page"),

    # -----------------------------------------------------------------------
    # REST API — service lifecycle
    # -----------------------------------------------------------------------
    path("api/globus/", views.list_services_api, name="list_api"),
    path("api/globus/create/", views.create_service_api, name="create_api"),
    path("api/globus/<int:service_id>/", views.get_service_api, name="get_api"),
    path("api/globus/<int:service_id>/delete/", views.delete_service_api, name="delete_api"),

    # -----------------------------------------------------------------------
    # REST API — Globus Auth flow
    # -----------------------------------------------------------------------
    path("api/globus/auth/url/", views.get_auth_url_api, name="auth_url_api"),
    path("api/globus/auth/callback/", views.auth_callback_api, name="auth_callback_api"),
    path("api/globus/auth/status/", views.auth_status_api, name="auth_status_api"),
    path("api/globus/auth/logout/", views.auth_logout_api, name="auth_logout_api"),

    # -----------------------------------------------------------------------
    # REST API — GCS wizard steps
    # -----------------------------------------------------------------------
    # Endpoint setup (interactive — returns command string for WebSocket execution)
    path("api/globus/<int:service_id>/endpoint/cmd/", views.get_endpoint_setup_cmd_api, name="endpoint_cmd_api"),
    # Collect deployment key after interactive endpoint setup completes
    path("api/globus/<int:service_id>/endpoint/deployment-key/", views.fetch_deployment_key_api, name="deployment_key_api"),
    # Manually set endpoint ID (when auto-extraction from deployment key fails)
    path("api/globus/<int:service_id>/endpoint/set-id/", views.set_endpoint_id_api, name="set_endpoint_id_api"),
    # GCS login command (interactive — required before gateway/collection creation)
    path("api/globus/<int:service_id>/login/cmd/", views.get_gcs_login_cmd_api, name="gcs_login_cmd_api"),
    # Transfer endpoint ownership to service account (interactive)
    path("api/globus/<int:service_id>/endpoint/set-owner/", views.set_endpoint_owner_api, name="set_owner_api"),
    # Node setup (non-interactive — node is launched as a new container with env vars)
    path("api/globus/<int:service_id>/node/setup/", views.setup_node_api, name="setup_node_api"),
    # Storage gateway creation (non-interactive after gcs login)
    path("api/globus/<int:service_id>/gateway/create/", views.create_gateway_api, name="create_gateway_api"),
    # Collection creation (non-interactive after gcs login)
    path("api/globus/<int:service_id>/collection/create/", views.create_collection_api, name="create_collection_api"),
    # Arbitrary exec (non-interactive)
    path("api/globus/<int:service_id>/exec/", views.exec_command_api, name="exec_api"),
    # Legacy endpoint setup route (kept for backward compat — redirects to cmd endpoint)
    path("api/globus/<int:service_id>/endpoint/setup/", views.setup_endpoint_api, name="setup_endpoint_api"),
]
