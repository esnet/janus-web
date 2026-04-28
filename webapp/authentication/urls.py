from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("signup/", views.signup_view, name="signup"),
    path("api/access-info/", views.get_access_info_api, name="get_access_info_api"),
    path("api/update-access/", views.update_access_api, name="update_access_api"),
    path("api/update-access-bulk/", views.update_access_bulk_api, name="update_access_bulk_api"),
    path("container/", views.access_control_dashboard, {"tab": "images"}, name="auth_images"),
    path("profiles/", views.access_control_dashboard, {"tab": "profiles"}, name="auth_profiles"),
    path("nodes/", views.access_control_dashboard, {"tab": "nodes"}, name="auth_nodes"),
    path("sessions/", views.access_control_dashboard, {"tab": "active"}, name="auth_sessions"),
]
