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

    def create_cmd(self, tool, dst_host, dst_port, sess, src_node, src_cid, dst_node, dst_cid):
        if tool == "iperf3":
            cmd = f"{tool} -s -D"
            _, exec_id = create_exec(dst_node, dst_cid, cmd, start=True)
            cmd = f"{tool} -c {dst_host} -i 2"
        elif tool == "escp":
            cmd = 'dd if=/dev/zero of=/tmp/10T bs=1 count=1 seek=1T'
            _, exec_id = create_exec(src_node, src_cid, cmd, start=True)
            cmd = f'escp -P {dst_port} --bits --direct --args_src="--engine=dummy -t 16 -b 1M" --args_dst="--engine=dummy -t 16 -b 1M" /tmp/10T {dst_host}:/tmp'
        elif tool == "xfer_test":
            cmd = f"{tool} -s"
            _, exec_id = create_exec(dst_node, dst_cid, cmd, start=True)
            cmd = f"{tool} -c {dst_host} -i 2"
        else:
            cmd = tool
        return cmd

    def send_done(self, sid, msg=None):
        rmsg = dict()
        rmsg["sid"] = sid
        rmsg["done"] = True
        rmsg["data"] = msg
        self.send_json(rmsg)

    def run_handler(self, msg):
        try:
            sess = msg.get("sess").get("data")
            sid = msg.get("sid")
            host = msg.get("hostname")
            tool = msg.get("tool")
            create = list()

            allocations = sess.get("allocations")
            services = sess.get("services")
            if len(allocations.keys()) < 2 and not host:
                return self.send_done(msg["sid"], "Cannot run test without destination")

            src_node = list(allocations.keys())[0]
            src_cid = allocations.get(src_node)[0]
            src_nid = services.get(src_node)[0].get("node_id")

            dst_node = list(allocations.keys())[1]
            dst_cid = allocations.get(dst_node)[0]
            dst_nid = services.get(dst_node)[0].get("node_id")

            dst_host = host if host else services.get(dst_node)[0].get('ctrl_host')
            hparts = dst_host.split(":")
            if len(hparts) > 1:
                dst_host = hparts[0]
                dst_port = hparts[1]
            else:
                dst_port = services.get(dst_node)[0].get("ctrl_port")

            cmd = self.create_cmd(tool, dst_host, dst_port, sess, src_node, src_cid, dst_node, dst_cid)
            _, exec_id = create_exec(src_node, src_cid, cmd)
            create.append({'node_id': src_nid,
                           'exec_id': exec_id})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self.send_done(msg["sid"], f"Error running test: {e}")

        _, jwt = get_auth_jwt()
        node_id = create[0]["node_id"]
        exec_id = create[0]["exec_id"]
        ws_url = f"{PORTAINER_WS}/api/websocket/exec?token={jwt}&id={exec_id}&endpointId={node_id}"
        ws = websocket.create_connection(ws_url)

        rmsg = dict()
        rmsg["sid"] = sid
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
        self.send_done(sid)
