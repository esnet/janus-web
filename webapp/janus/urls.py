from django.urls import path

from . import views

app_name = "janus"
urlpatterns = [
    path("session/", views.list_sessions, name="list_sessions"),
    path("api/sessions/", views.get_sessions_api, name="get_sessions_api"),
    path("api/sessions/create/", views.create_session_api, name="create_session_api"),
    path("api/sessions/<int:session_id>/update/", views.update_session_api, name="update_session_api"),
    path("api/sessions/<int:session_id>/apply/", views.apply_session_changes_api, name="apply_session_changes_api"),
    path("api/sessions/<int:session_id>/start/", views.start_session_api, name="start_session_api"),
    path("api/sessions/<int:session_id>/stop/", views.stop_session_api, name="stop_session_api"),
    path("api/sessions/<int:session_id>/delete/", views.delete_session_api, name="delete_session_api"),
    path("api/sessions/<int:session_id>/logs/<str:nname>/", views.view_log, name="get_logs_api"),
    path("api/nodes/", views.get_nodes_api, name="get_nodes_api"),
    path("api/images/", views.get_images_api, name="get_images_api"),
    path("api/nodes/add/", views.add_node_api, name="add_node_api"),
    path("api/nodes/remove/<str:nname>/", views.remove_node_api, name="remove_node_api"),
    path("api/node-types/", views.get_node_types_api, name="get_node_types_api"),
    path("api/profile-choices/", views.get_profile_choices_api, name="get_profile_choices_api"),
    path("api/profiles/<str:resource>/", views.get_profiles_api, name="get_profiles_api"),
    path("api/profiles/<str:resource>/create/", views.create_profile_api, name="create_profile_api"),
    path("api/profiles/<str:resource>/update/", views.update_profile_api, name="update_profile_api"),
    path("api/profiles/<str:resource>/delete/<str:pname>/", views.delete_profile_api, name="delete_profile_api"),
    path("session/start/<int:session_id>/", views.start_session, name="start_session"),
    path("session/stop/<int:session_id>/", views.stop_session, name="stop_session"),
    path(
        "session/delete/<int:session_id>/", views.delete_session, name="delete_session"
    ),
    path("session/create/", views.create_session, name="create_session"),
    path("session/<int:session_id>/", views.view_session, name="view_session"),
    path("session/<int:session_id>/logs/<str:nname>", views.view_log, name="view_log"),
    path("profiles/", views.list_profiles, name="list_profiles"),
    path("profiles/refresh/", views.refresh_profiles, name="refresh_profiles"),
    path("profiles/create/<str:resource>", views.create_profile, name="create_profile"),
    path("profiles/update/<str:resource>", views.update_profile, name="update_profile"),
    path(
        "profiles/delete/<str:resource>/<str:pname>",
        views.delete_profile,
        name="delete_profile",
    ),
    path("nodes/", views.list_nodes, name="list_nodes"),
    path("nodes/add/", views.add_node, name="add_node"),
    path("nodes/refresh/", views.refresh_node, name="refresh_node"),
    path("nodes/remove/<str:nname>", views.remove_node, name="remove_node"),
]
