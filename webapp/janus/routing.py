from django.urls import re_path
from . import consumers


websocket_urlpatterns = [
    re_path(r"ws/events/$", consumers.EventConsumer.as_asgi()),
    re_path(r"ws/perf/$", consumers.PerfConsumer.as_asgi()),
    re_path(r"ws/asyncperf/$", consumers.AsyncPerfConsumer.as_asgi()),
]
