from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path('container/', views.image_access_control, name='auth_images'),
    path('profiles/', views.profile_access_control, name='auth_profiles'),
    path('nodes/', views.node_access_control, name='auth_nodes'),
    path('sessions/', views.sessions_access_control, name='auth_sessions'),
]