import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
import janus.routing
import globus_service.routing


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")
django_asgi_app = get_asgi_application()

# Combine WebSocket URL patterns from all apps
websocket_urlpatterns = (
    janus.routing.websocket_urlpatterns
    + globus_service.routing.websocket_urlpatterns
)

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
