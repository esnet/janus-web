import json
import time
from channels.generic.websocket import WebsocketConsumer


class PerfConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()

    def disconnect(self, close_code):
        pass

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]
        time.sleep(2);
        message['command'] = 'done'
        self.send(text_data=json.dumps({"message": message}))
