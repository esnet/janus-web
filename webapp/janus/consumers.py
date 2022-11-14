import json
import time
import threading
import websocket
from .services import create_exec, get_auth_jwt
from webapp.settings import PORTAINER_WS
from asgiref.sync import sync_to_async
from channels.generic.websocket import JsonWebsocketConsumer, AsyncJsonWebsocketConsumer

class AsyncPerfConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        await self.close()

    async def receive_json(self, data):
        await self.send_json(data)


class PerfConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.accept()

    def disconnect(self, close_code):
        self.close()

    def receive_json(self, data):
        self.th = threading.Thread(target=self.run_handler, args=(data,))
        self.th.start()

    def create_cmd(self, tool, host, sess):
        if tool == "iperf3":
            cmd = f"{tool} -c {host} -i 2"
        else:
            cmd = tool
        return cmd

    def run_handler(self, msg):
        try:
            sess = msg.get("sess").get("data")
            host = msg.get("hostname")
            tool = msg.get("tool")
            cmd = self.create_cmd(tool, host, sess)
            create = list()
            for nname,cids in sess.get("allocations").items():
                for c in cids:
                    nid = sess.get("services").get(nname)[0].get("node_id")
                    _, exec_id = create_exec(nname, c, cmd)
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
        rmsg["sid"] = msg["sid"]
        while True:
            try:
                msg = ws.recv()
                rmsg["done"] = False
                rmsg["data"] = msg
                #sync_to_async(self.send_json)(rmsg)
                self.send_json(rmsg)
            except:
                ws.close()
                break

        rmsg["done"] = True
        rmsg["data"] = None
        self.send_json(rmsg)
