import os

from django.core.asgi import get_asgi_application

# django.setup() must run before importing app modules that reference models.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402
import janus.routing  # noqa: E402
import globus_service.routing  # noqa: E402

# Combine WebSocket URL patterns from all apps
websocket_urlpatterns = (
    janus.routing.websocket_urlpatterns
    + globus_service.routing.websocket_urlpatterns
)

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
