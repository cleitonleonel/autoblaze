import time
import json
import websocket


class WebSocketClient(object):

    def __init__(self, api):
        self.api = api
        self.wss = websocket.WebSocketApp(
            self.api.wss_url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open,
            on_ping=self.on_ping,
            on_pong=self.on_pong,
            header=self.api.headers
        )
        websocket.enableTrace(self.api.trace_ws)

    def on_open(self, ws):
        message = '%d["cmd", {"id": "subscribe", "payload": {"room": "double_v2"}}]' % 421
        ws.send(message)

    def on_message(self, ws, message):
        if "double.tick" in message:
            self.api.ws_response = json.loads(message[2:])[1]["payload"]

    def on_error(self, ws, error):
        pass

    def on_close(self, ws, close_status_code, close_msg):
        time.sleep(1)
        self.api.websocket_closed = True

    def on_ping(self, ws, message):
        pass

    def on_pong(self, ws, message):
        ws.send("3")
