"""
consumers.py — WebSocket consumer for interactive GCS container sessions.

GCSInteractiveConsumer bridges the browser and the Janus Controller WebSocket
exec stream, providing bidirectional stdin/stdout for interactive GCS CLI
commands (e.g., those that prompt for a Globus Auth code).

Route: ws/gcs-interactive/<service_id>/
"""

import ssl
import json
import queue
import logging
import threading

import websocket
from django.conf import settings
from channels.generic.websocket import JsonWebsocketConsumer

from .models import GlobusService

logger = logging.getLogger(__name__)

_SENTINEL = object()  # signals the send thread to stop


class GCSInteractiveConsumer(JsonWebsocketConsumer):
    """
    WebSocket consumer that:
      1. Authenticates the connecting user.
      2. Looks up the GlobusService by service_id from the URL route.
      3. Creates an exec session on the Janus Controller for the service's container.
      4. Proxies stdout from the controller WS to the browser.
      5. Proxies stdin from the browser to the controller WS.

    The websocket-client library is NOT thread-safe for concurrent send/recv on
    the same connection.  We therefore use two dedicated threads:
      - _recv_thread: blocks on ctrl_ws.recv() and forwards output to the browser.
      - _send_thread: blocks on a queue and forwards browser stdin to ctrl_ws.send().

    Message protocol (browser → server):
        {"type": "stdin",  "data": "<text to send to container>"}
        {"type": "resize", "cols": <int>, "rows": <int>}
        {"type": "exec",   "cmd":  "<command to run>"}

    Message protocol (server → browser):
        {"type": "stdout", "data": "<output text>"}
        {"type": "error",  "data": "<error message>"}
        {"type": "done"}
    """

    def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            logger.warning("GCSInteractiveConsumer: unauthenticated connection rejected")
            self.close()
            return

        service_id = self.scope["url_route"]["kwargs"].get("service_id")
        try:
            self.service = GlobusService.objects.get(pk=service_id, user=user)
        except GlobusService.DoesNotExist:
            logger.warning(
                "GCSInteractiveConsumer: service %s not found for user %s",
                service_id,
                user.username,
            )
            self.close()
            return

        self.accept()
        self._ctrl_ws = None
        self._send_queue = queue.Queue()   # browser stdin → container
        self._stop_event = threading.Event()
        logger.info(
            "GCSInteractiveConsumer: connected for service %s (user=%s)",
            service_id,
            user.username,
        )

    def disconnect(self, close_code):
        self._stop_event.set()
        # Unblock the send thread
        self._send_queue.put(_SENTINEL)
        if self._ctrl_ws:
            try:
                self._ctrl_ws.close()
            except Exception:
                pass
        logger.info("GCSInteractiveConsumer: disconnected (code=%s)", close_code)

    def receive_json(self, content):
        msg_type = content.get("type")

        if msg_type == "exec":
            cmd = content.get("cmd", "").strip()
            if not cmd:
                self.send_json({"type": "error", "data": "Empty command"})
                return
            self._start_exec_stream(cmd)

        elif msg_type == "stdin":
            # Enqueue stdin — the send thread forwards it to the controller WS
            data = content.get("data", "")
            if self._ctrl_ws:
                self._send_queue.put(data)
            else:
                self.send_json({"type": "error", "data": "No active exec session"})

        elif msg_type == "resize":
            # Best-effort resize forwarding via the send queue
            if self._ctrl_ws:
                resize_msg = json.dumps({
                    "type": "resize",
                    "cols": content.get("cols", 80),
                    "rows": content.get("rows", 24),
                })
                self._send_queue.put(resize_msg)

        else:
            self.send_json({"type": "error", "data": f"Unknown message type: {msg_type}"})

    # ------------------------------------------------------------------
    # Internal: exec stream management
    # ------------------------------------------------------------------

    def _start_exec_stream(self, cmd: str):
        """
        Create an exec on the Janus Controller and open a WebSocket stream to it.
        Starts two background threads: one for recv (output) and one for send (stdin).
        """
        import shlex
        import httpx

        exec_data = {
            "node": self.service.node_name,
            "container": self.service.container_id,
            "Cmd": shlex.split(cmd),
            "attach": True,
            "tty": True,
            "start": False,
        }
        try:
            res = httpx.post(
                url=settings.JANUS_CONTROLLER_URL + "api/janus/controller/exec",
                json=exec_data,
                auth=settings.JANUS_CONTROLLER_AUTH,
                verify=settings.CTRL_SSL_VERIFY,
                timeout=30.0,
            )
            if res.status_code not in (200, 201):
                self.send_json({"type": "error", "data": f"Exec create failed: {res.text}"})
                return
            exec_id = res.json().get("Id")
            node_id = res.json().get("node_id", "")
        except Exception as exc:
            self.send_json({"type": "error", "data": f"Exec create error: {exc}"})
            return

        self._stop_event.clear()
        # Drain any stale items from a previous session
        while not self._send_queue.empty():
            try:
                self._send_queue.get_nowait()
            except queue.Empty:
                break

        recv_thread = threading.Thread(
            target=self._recv_loop,
            args=(exec_id, node_id),
            daemon=True,
        )
        recv_thread.start()

    def _recv_loop(self, exec_id: str, node_id: str):
        """
        Background thread: connect to the Janus Controller WebSocket,
        send the exec start message, then:
          - spawn a send thread to forward stdin from _send_queue → ctrl_ws
          - relay stdout from ctrl_ws → browser
        """
        ws_url = f"{settings.JANUS_CONTROLLER_WS_URL}/ws"
        try:
            ctrl_ws = websocket.create_connection(
                ws_url,
                sslopt={"cert_reqs": ssl.CERT_NONE},
            )
            self._ctrl_ws = ctrl_ws

            # Send the exec start message
            start_msg = {
                "type": 0,
                "node": self.service.node_name,
                "node_id": node_id,
                "container": self.service.container_id,
                "exec_id": exec_id,
            }
            ctrl_ws.send(json.dumps(start_msg))

            # Start the send thread (stdin forwarding)
            send_thread = threading.Thread(
                target=self._send_loop,
                args=(ctrl_ws,),
                daemon=True,
            )
            send_thread.start()

            # Relay output until the stream closes or stop is requested
            while not self._stop_event.is_set():
                try:
                    ctrl_ws.settimeout(1.0)
                    raw = ctrl_ws.recv()
                    if raw:
                        self.send_json({"type": "stdout", "data": raw})
                except websocket.WebSocketTimeoutException:
                    continue
                except Exception as exc:
                    logger.debug("GCSInteractiveConsumer: recv stream ended: %s", exc)
                    break

            # Signal the send thread to stop
            self._send_queue.put(_SENTINEL)
            send_thread.join(timeout=2)
            ctrl_ws.close()

        except Exception as exc:
            logger.error("GCSInteractiveConsumer: stream error: %s", exc)
            try:
                self.send_json({"type": "error", "data": str(exc)})
            except Exception:
                pass
        finally:
            self._ctrl_ws = None
            try:
                self.send_json({"type": "done"})
            except Exception:
                pass

    def _send_loop(self, ctrl_ws):
        """
        Background thread: drain _send_queue and forward each item to ctrl_ws.
        Stops when it receives the _SENTINEL value or the stop event is set.
        """
        while not self._stop_event.is_set():
            try:
                item = self._send_queue.get(timeout=0.5)
                if item is _SENTINEL:
                    break
                ctrl_ws.send(item)
            except queue.Empty:
                continue
            except Exception as exc:
                logger.error("GCSInteractiveConsumer: send error: %s", exc)
                break
