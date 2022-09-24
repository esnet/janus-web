from django.urls import path

from . import views

urlpatterns = [
    path('start/<int:session_id>/', views.start_session, name='start_session'),
    path('stop/<int:session_id>/', views.stop_session, name='stop_session'),
    path('delete/<int:session_id>/', views.delete_session, name='delete_session'),
    path('create/', views.create_session, name='create_session'),
    path('<int:session_id>/', views.view_session, name='view_session'),
    path('', views.list_sessions, name='list_sessions'),
    path('profiles/', views.list_profiles, name='list_profiles'),
]