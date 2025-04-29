import ssl
import json
import time
import threading
import websocket
from django.conf import settings
from .services import create_exec, get_auth_jwt
#from webapp.settings import PORTAINER_WS
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

    def create_cmd(self, tool, dst_host, dst_port, sess,
                   src_node, src_cid, dst_node, dst_cid, duration=None):
        img = sess.get("request")[0].get("image")
        img = img.split(":")[0] # remove any tags

        if tool == "iperf3":
            cmd = f"{tool} -s -D"
            if dst_node:
                _, exec_id = create_exec(dst_node, dst_cid, cmd)
            cmd = f"{tool} -c {dst_host} -i 2"
            if duration:
                cmd += f" -t {duration}"
            if dst_port:
                cmd += f" -p {dst_port}"
        elif tool == "iperf3_server":
            cmd = f"iperf3 -s -1"
            if dst_port:
                cmd += f" -p {dst_port}"
        elif tool == "escp":
            dst_port = dst_port if dst_port else "22"
            cmd = 'dd if=/dev/zero of=/tmp/10T bs=1 count=1 seek=10T'
            _, exec_id = create_exec(src_node, src_cid, cmd)
            cmd = f'escp -P {dst_port} --bits --direct --args_src="--engine=dummy -t 16 -b 1M" --args_dst="--engine=dummy -t 16 -b 1M" /tmp/10T {dst_host}:/tmp'
        elif tool == "xfer_test" and img.endswith("dtnaas/tools"):
            cmd = f"{tool} -s"
            if dst_node:
                _, exec_id = create_exec(dst_node, dst_cid, cmd)
            cmd = f"{tool} -c {dst_host} -t 20 -i 2 -a 1 -o 20"
            if duration:
                cmd += f" -t {duration}"
            if dst_port:
                cmd += f" -p {dst_port}"
        elif tool == "xfer_test" and img.endswith("dtnaas/ofed"):
            cmd = f"{tool} -s -r -d 128"
            if dst_node:
                _, exec_id = create_exec(dst_node, dst_cid, cmd)
            cmd = f"{tool} -c {dst_host} -t 20 -i 2 -a 1 -o 24 -d 128 -r"
            if duration:
                cmd += f" -t {duration}"
            if dst_port:
                cmd += f" -p {dst_port}"
        elif tool == "ib_write_bw":
            cmd = "ib_write_bw -R -a"
            if dst_node:
                _, exec_id = create_exec(dst_node, dst_cid, cmd)
            cmd = f"ib_write_bw --report_gbits -n 10000 -F -a -t 2048 -R {dst_host}"
        else:
            cmd = tool
        return f"stdbuf -o0 -e0 {cmd}"

    def send_done(self, sid, msg=None):
        rmsg = dict()
        rmsg["sid"] = sid
        rmsg["done"] = True
        rmsg["data"] = msg
        self.send_json(rmsg)

    def run_handler(self, msg):
        try:
            sess = msg.get("sess").get("data")
            overrides = sess.get('overrides')
            sid = msg.get("sid")
            host = msg.get("hostname")
            duration = msg.get("duration")
            tool = msg.get("tool")
            create = list()

            has_dest = False
            services = sess.get("services")
            if len(services.keys()) > 1:
                has_dest = True
            else:
                for k,v in services.items():
                    if len(v) > 1:
                        has_dest = True

            if not has_dest and not host:
                return self.send_done(msg["sid"], "Cannot run test without destination")

            src_node = list(services.keys())[0]
            src_cid = services.get(src_node)[0].get('container_id')
            src_nid = services.get(src_node)[0].get("node_id")

            if len(services.keys()) > 1:
                dst_node = list(services.keys())[1]
                dst_cid = services.get(dst_node)[0].get('container_id')
                dst_nid = services.get(dst_node)[0].get("node_id")
                dst_host = services.get(dst_node)[0].get("ctrl_host")
                dst_port = services.get(dst_node)[0].get("ctrl_port")

                service = services.get(dst_node)[0]
                if service.get("data_net"):
                   dst_host = service.get("data_ipv4") if service.get("data_ipv4") else service.get("data_ipv6")

                if overrides and overrides.get(dst_host) and overrides[dst_host].get('ip_addr'):
                    dst_host = overrides[dst_host]['ip_addr']
            elif has_dest:
                dst_node = src_node
                dst_cid = services.get(src_node)[1].get('container_id')
                dst_nid = services.get(src_node)[1].get("node_id")
                dst_host = services.get(src_node)[1].get("ctrl_host")
                dst_port = services.get(src_node)[1].get("ctrl_port")

                service = services.get(src_node)[1]
                if service.get("data_net"):
                   dst_host = service.get("data_ipv4") if service.get("data_ipv4") else service.get("data_ipv6")

                if overrides and overrides.get(dst_host) and overrides[dst_host].get('ip_addr'):
                    dst_host = overrides[dst_host]['ip_addr']
            else:
                dst_node = None
                dst_cid = None
                dst_nid = None
                dst_port = None
                dst_host = None

            if host:
                dst_host = host

            hparts = dst_host.split(":")
            if len(hparts) > 1:
                dst_host = hparts[0]
                dst_port = hparts[1]
            elif host and not tool == "escp":
                dst_port = None

            # XXX only set dst port to control port for escp
            if not host and not tool == "escp":
                dst_port = None

            cmd = self.create_cmd(tool, dst_host, dst_port, sess, src_node, src_cid, dst_node, dst_cid, duration)
            _, exec_id = create_exec(src_node, src_cid, cmd, tty=True, start=False)
            create.append({'node': src_node,
                           'node_id': src_nid,
                           'exec_id': exec_id,
                           'cont_id': src_cid})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self.send_done(msg["sid"], f"Error running test: {e}")

        #_, jwt = get_auth_jwt()
        node = create[0]["node"]
        node_id = create[0]["node_id"]
        exec_id = create[0]["exec_id"]
        cont_id = create[0]["cont_id"]
        #ws_url = f"{PORTAINER_WS}/api/websocket/exec?token={jwt}&id={exec_id}&endpointId={node_id}"
        #ws = websocket.create_connection(ws_url)

        ws_url = f"{settings.JANUS_CONTROLLER_WS_URL}/ws"
        ws = websocket.create_connection(ws_url, sslopt={"cert_reqs": ssl.CERT_NONE})
        # send the message to get the active exec stream from the controller
        msg = {"type": 0,
               "node": node,
               "node_id": node_id,
               "container": cont_id,
               "exec_id": exec_id}
        ws.send(json.dumps(msg))

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
