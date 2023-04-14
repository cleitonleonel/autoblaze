import time
import json
import requests
from pathlib import Path
from threading import Thread
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from core.http.hcaptcha import hcaptcha_solver
from core.ws.client import WebSocketClient

URL_BASE = "https://blaze.com"
WSS_BASE = "wss://api-v2.blaze.com"
URL_HCAPTCHA_API = "http://127.0.0.1:9001"
SITE_KEY = "75d69f30-f408-4793-952d-a887196efe8d"
VERSION_API = "0.0.1-professional"

retry_strategy = Retry(
    connect=3,
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504, 104, 403],
    method_whitelist=["HEAD", "POST", "PUT", "GET", "OPTIONS"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)


def datetime_to_ms_epoch():
    timestamp_secs = time.time()
    return int(timestamp_secs * 1000)


class Response(object):

    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


class Browser(object):

    def __init__(self):
        self.response = None
        self.headers = None
        self.session = requests.Session()

    def set_headers(self, headers=None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/87.0.4280.88 Safari/537.36"
        }
        if headers:
            for key, value in headers.items():
                self.headers[key] = value

    def get_headers(self):
        return self.headers

    def send_request(self, method, url, **kwargs):
        try:
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)
            return self.session.request(method, url, **kwargs)
        except requests.exceptions.ConnectionError:
            return Response({"result": False,
                             "object": self.response,
                             "message": "Network Unavailable. Check your connection."
                             }, 104)


class BlazeClientAPI(Browser):
    websocket_thread = None
    websocket_client = None
    websocket_closed = None
    ws_response = None
    is_logged = False
    trace_ws = False
    filename = None

    def __init__(self, username=None, password=None):
        super().__init__()
        self.proxies = None
        self.token = None
        self.wallet_id = None
        self.username = username
        self.password = password
        self.set_headers()
        self.headers = self.get_headers()
        self.wss_url = f"{WSS_BASE}/replication/?EIO=3&transport=websocket"

    @property
    def websocket(self):
        return self.websocket_client.wss

    def authorization(self, token=None):
        if token:
            self.token = token
            self.is_logged = True
        else:
            return self.auth()
        return True, "Token em execução..."

    def auth(self):
        data = {
            "username": self.username,
            "password": self.password
        }
        params = {
            "analyticSessionID": datetime_to_ms_epoch()
        }
        self.headers["x-captcha-response"] = self.get_captcha_token()
        self.headers["referer"] = f"{URL_BASE}/pt/?modal=auth&tab=login"
        self.response = self.send_request("PUT",
                                          f"{URL_BASE}/api/auth/password",
                                          json=data,
                                          params=params,
                                          headers=self.headers)
        if self.response.json().get("error"):
            return False, self.response.json().get("error")["message"]
        self.token = self.response.json()["access_token"]
        self.is_logged = True
        data["access_token"] = self.token
        json_object = json.dumps(data, indent=4)
        output_file = Path(self.filename)
        output_file.parent.mkdir(exist_ok=True, parents=True)
        output_file.write_text(json_object)
        return True, self.response.json()

    def reconnect(self):
        return self.auth()

    def hcaptcha_response(self):
        print("Using Anticaptcha System !!!")
        self.headers = self.get_headers()
        self.response = self.send_request("GET",
                                          f"{URL_HCAPTCHA_API}/hcaptcha/token",
                                          headers=self.headers)
        if self.response:
            return self.response.json().get("x-captcha-response")
        return None

    def get_captcha_token(self):
        site_url = f"{URL_BASE}/api/auth/password"
        response_result = self.hcaptcha_response()
        if not response_result:
            response_result = hcaptcha_solver(site_url, SITE_KEY)
        return response_result

    def get_profile(self):
        self.headers["authorization"] = f"Bearer {self.token}"
        self.response = self.send_request("GET",
                                          f"{URL_BASE}/api/users/me",
                                          headers=self.headers)
        if not self.response.json().get("error"):
            self.is_logged = True
        return self.response.json()

    def get_balance(self):
        self.headers["authorization"] = f"Bearer {self.token}"
        self.response = self.send_request("GET",
                                          f"{URL_BASE}/api/wallets",
                                          headers=self.headers)
        if self.response.status_code == 502:
            self.reconnect()
            return self.get_balance()
        elif self.response:
            self.wallet_id = self.response.json()[0]["id"]
        return self.response.json()

    def get_user_info(self):
        result_dict = {}
        balance = self.get_balance()
        user_info = self.get_profile()
        result_dict["username"] = user_info["username"]
        result_dict["balance"] = balance[0]["balance"]
        result_dict["wallet_id"] = balance[0]["id"]
        result_dict["tax_id"] = user_info["tax_id"]
        return result_dict

    def get_status(self):
        self.response = self.ws_response
        if self.response:
            return self.response["status"]
        return {"status": "unknown"}

    def double_bets(self, color, amount):
        result_dict = {
            "result": False,
        }
        data = {
            "amount": str(f"{float(amount):.2f}"),
            "currency_type": "BRL",
            "color": 1 if color == "vermelho" else 2 if color == "preto" else 0,
            "free_bet": False,
            "wallet_id": self.wallet_id
        }
        self.headers["authorization"] = f"Bearer {self.token}"
        self.response = self.send_request("POST",
                                          f"{URL_BASE}/api/roulette_bets",
                                          json=data,
                                          headers=self.headers)
        if self.response:
            result_dict = {
                "result": True,
                "object": self.response,
                "message": "Operação realizada com sucesso!!!"
            }
        return result_dict

    async def awaiting_double(self, verbose=True):
        while True:
            try:
                self.response = self.ws_response
                if verbose:
                    print(f'\rSTATUS: {self.response["status"]}', end="")
                if self.response["color"] is not None and self.response["roll"] is not None:
                    return self.response
            except:
                pass
            time.sleep(0.1)

    async def get_double(self):
        result_dict = None
        data = await self.awaiting_double(verbose=False)
        if data:
            result_dict = {
                "roll": data["roll"],
                "color": data["color"]
            }
        return result_dict

    def get_last_doubles(self):
        self.response = self.send_request("GET",
                                          f"{URL_BASE}/api/roulette_games/recent",
                                          proxies=self.proxies,
                                          headers=self.headers)
        if self.response:
            result = {
                "items": [
                    {"color": "branco" if i["color"] == 0 else "vermelho" if i["color"] == 1 else "preto",
                     "value": i["roll"], "created_date": datetime.strptime(
                        i["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d %H:%M:%S")
                     } for i in self.response.json()]}
            return result
        return False

    def get_last_crashs(self):
        self.response = self.send_request("GET",
                                          f"{URL_BASE}/api/crash_games/recent",
                                          proxies=self.proxies,
                                          headers=self.headers)
        if self.response:
            result = {
                "items": [{"color": "preto" if float(i["crash_point"]) < 2 else "verde", "value": i["crash_point"]}
                          for i in self.response.json()]}
            return result
        return False

    def get_roulettes(self):
        self.response = self.send_request("GET",
                                          f"{URL_BASE}/api/roulette_games/current",
                                          proxies=self.proxies,
                                          headers=self.headers)
        return self.response

    def start_websocket(self):
        self.websocket_client = WebSocketClient(self)
        self.websocket_thread = Thread(
            target=self.websocket.run_forever,
            kwargs={
                'ping_interval': 24,
                'ping_timeout': 5,
                'ping_payload': "2",
                'origin': 'https://blaze.com',
                'host': 'api-v2.blaze.com',
            }
        )
        self.websocket_thread.daemon = True
        self.websocket_thread.start()

    def close(self):
        if self.websocket_client:
            self.websocket.close()
            self.websocket_thread.join()

    def websocket_alive(self):
        return self.websocket_thread.is_alive()
