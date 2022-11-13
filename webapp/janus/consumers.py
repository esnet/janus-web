import json
import time
import websocket
from .services import create_exec, get_auth_jwt
from webapp.settings import PORTAINER_WS
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.generic.websocket import WebsocketConsumer


class PerfConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()

    def disconnect(self, close_code):
        pass

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        try:
            message = text_data_json.get("message")
            sess = message.get("sess").get("data")
            command = message.get("command")
            create = list()
            for nname,cids in sess.get("allocations").items():
                for c in cids:
                    nid = sess.get("services").get(nname)[0].get("node_id")
                    _, exec_id = create_exec(nname, c, command)
                    create.append({'node_id': nid,
                                   'exec_id': exec_id})
        except Exception as e:
            import traceback
            traceback.print_exc()

        _, jwt = get_auth_jwt()
        node_id = create[0]["node_id"]
        exec_id = create[0]["exec_id"]
        ws_url = f"{PORTAINER_WS}/api/websocket/exec?token={jwt}&id={exec_id}&endpointId={node_id}"
        ws = websocket.create_connection(ws_url)

        rmsg = dict()
        rmsg["sid"] = message["sid"]
        while True:
            try:
                msg = ws.recv()
                print (msg)
                rmsg["done"] = False
                rmsg["data"] = msg
                self.send(text_data=json.dumps({"message": rmsg}).replace(r'\u0000', ''))
            except:
                ws.close()
                break

        rmsg["done"] = True
        rmsg["data"] = None
        self.send(text_data=json.dumps({"message": rmsg}))
