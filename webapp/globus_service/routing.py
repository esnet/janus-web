from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/gcs-interactive/(?P<service_id>\d+)/$",
        consumers.GCSInteractiveConsumer.as_asgi(),
    ),
]
