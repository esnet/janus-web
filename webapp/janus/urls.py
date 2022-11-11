from django.urls import path

from . import views

app_name = "janus"
urlpatterns = [
    path('session/', views.list_sessions, name='list_sessions'),
    path('session/start/<int:session_id>/', views.start_session, name='start_session'),
    path('session/stop/<int:session_id>/', views.stop_session, name='stop_session'),
    path('session/delete/<int:session_id>/', views.delete_session, name='delete_session'),
    path('session/create/', views.create_session, name='create_session'),
    path('session/<int:session_id>/', views.view_session, name='view_session'),
    path('profiles/', views.list_profiles, name='list_profiles'),
    path('profiles/create/', views.create_profile, name='create_profile'),
    path('profiles/update/', views.update_profile, name='update_profile'),
    path('profiles/delete/<str:pname>/', views.delete_profile, name='delete_profile'),
    path('nodes/', views.list_nodes, name='list_nodes'),
    path('nodes/add/', views.add_node, name='add_node'),
    path('nodes/remove/<str:nname>', views.remove_node, name='remove_node'),
]
