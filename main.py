import os
import math
import json
import signal
import asyncio
import time
import warnings
import configparser
from yaspin import yaspin
from yaspin.spinners import Spinners
from typing import List, Dict
from datetime import datetime
from rich import print as rich_print
from core.http.api import BlazeClientAPI

__author__ = "Cleiton Leonel Creton"
__version__ = "0.0.1"

__message__ = f"""
Use com moderação, pois gerenciamento é tudo!
suporte: cleiton.leonel@gmail.com ou +55 (27) 9 9577-2291
"""

config = configparser.ConfigParser()
config.read('settings/config.ini', encoding="utf-8")

user = config.get("authentication", "user")
password = config.get("authentication", "password")

meta = config.getfloat("bets", "meta")
is_demo = config.getboolean("bets", "is_demo")
orders = json.loads(config.get("bets", "orders"))
demo_balance = config.getfloat("bets", "demo_balance")
stop_if_white = config.getboolean("bets", "stop_if_white")
force_stop_bets = config.getboolean("bets", "force_stop_bets")
preview_roulette = config.getboolean("bets", "preview_roulette")
stop_rounds_quantity = config.getint("bets", "stop_rounds_quantity")

art_effect = f"""
 █████╗ ██╗   ██╗████████╗ ██████╗ ██████╗ ██╗      █████╗ ███████╗███████╗
██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔══██╗██║     ██╔══██╗╚══███╔╝██╔════╝
███████║██║   ██║   ██║   ██║   ██║██████╔╝██║     ███████║  ███╔╝ █████╗  
██╔══██║██║   ██║   ██║   ██║   ██║██╔══██╗██║     ██╔══██║ ███╔╝  ██╔══╝  
██║  ██║╚██████╔╝   ██║   ╚██████╔╝██████╔╝███████╗██║  ██║███████╗███████╗
╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝
        author: {__author__} versão: {__version__}
        {__message__}
"""

rich_print(f"[italic red]{art_effect}[/italic red]")


def config_reload():
    config.read('settings/config.ini', encoding="utf-8")
    return json.loads(config.get("bets", "orders"))


def refresh_display():
    os.system('cls' if os.name == 'nt' else 'export TERM=xterm && clear > /dev/null')


def get_timer(_format='%Y-%m-%d %H:%M:%S'):
    return datetime.now().strftime(_format)


def truncate(f, n):
    return math.floor(f * 10 ** n) / 10 ** n


class Roulette(object):
    report_data = []
    result_bet = {}
    result_protection = {}
    bot_data = {}
    last_doubles = []
    user_info = {}
    balance = None
    cycle_balance = None
    current_balance = None
    first_balance = None
    meta = None
    colors = {
        0: "branco",
        1: "vermelho",
        2: "preto"
    }

    def __init__(self):
        self.client = BlazeClientAPI(user, password)
        self.is_betting = False
        self.profit = None
        self.count_win = 0
        self.count_loss = 0
        self.score_message = None
        self.count_martingale = 0
        self.scheduled_gale = False
        self.scheduled_amount = 0
        self.scheduled_protection_amount = 0
        self.green_percent = None
        self.red_percent = None
        self.orders = None
        self.quantity_rounds = 0
        self.count_number_after_word = 0
        self.count_number_stop_after_word = 0
        self.session_path = f"session/{user.split('@')[0]}_token.json"
        self.client.trace_ws = False
        self.client.start_websocket()
        self.welcome()

    def check_token(self) -> str:
        data = {}
        if os.path.isfile(self.session_path):
            with open(self.session_path) as file:
                data = json.loads(file.read())
        token = data.get("access_token")
        return token

    def connect(self) -> bool:
        with yaspin(text="Loading", color="red") as spinner:
            time.sleep(3)
            spinner.text = ""
            if not is_demo:
                token = self.check_token()
                self.client.filename = self.session_path
                check, message = self.client.authorization(token)
                if not check:
                    spinner.fail(f"💥 Falha de Autenticação.")
                    rich_print(f"[italic bold red]{message}[/italic bold red]")
                    return False
                spinner.ok("✅ Conectado com Sucesso!")
                return True
            return False

    def welcome(self) -> None:
        global is_demo
        self.balance = demo_balance
        if self.connect():
            self.balance = self.client.get_balance()
            self.user_info = self.client.get_user_info()
        self.first_balance = truncate(float(self.user_info.get("balance", 0)), 2) \
            if not is_demo else truncate(float(self.balance), 2)
        self.cycle_balance = self.first_balance
        self.meta = truncate(self.first_balance + meta, 2)
        rich_print(f"\n[italic green]Seja bem vindo(a) {self.user_info.get('username', '')}!!!"
                   f"\nSeu saldo inicial é de R$ {self.first_balance} "
                   f"\nSua meta ao final da operação "
                   f"é de R$ {self.meta} "
                   f"\nVocê está usando uma conta "
                   f"{'REAL[/italic green]' if not is_demo else 'DEMO[/italic green]'}\n"
                   )

    def strategy_analise(self) -> Dict:
        result_dict = {}
        self.orders = orders
        for order in self.orders:
            start = datetime.strptime(order[0], '%H:%M')
            end = datetime.strptime(order[1], '%H:%M')
            diff = int((end - start).total_seconds() / 60) * 2
            result_dict[order[0]] = diff + 2
        return result_dict

    async def run(self) -> None:
        enter = None
        stop_loop = asyncio.Event()
        strategy_result = self.strategy_analise()
        while not stop_loop.is_set():
            if self.quantity_rounds == 0:
                self.current_balance = self.first_balance
                enter = self.calculate_enter()
                hour = get_timer('%H:%M')
                self.quantity_rounds = strategy_result.get(hour, 0)
                if self.quantity_rounds > 0:
                    strategy_result.pop(hour)
                    if force_stop_bets:
                        self.quantity_rounds = stop_rounds_quantity
            if self.awaiting_status("waiting"):
                with yaspin(Spinners.timeTravel, text="Aguardando...") as sp:
                    await asyncio.sleep(1.5)
                # print(f"\rStatus: Waiting {get_timer()}", end="")
                if self.quantity_rounds > 0:
                    result_bets = await self.double_bets(enter)
                    if not result_bets["object"]["win"]:
                        self.current_balance = result_bets["object"]["balance"]
                        self.profit = self.calculate_profit()
                        enter = self.calculate_enter()
                        self.quantity_rounds -= 1
                    else:
                        print(f"\rWin !!!\r")
                        self.count_win += 1
                        self.profit = self.calculate_profit()
                        if stop_if_white:
                            print("Parando sistema...")
                            stop_loop.set()
                        self.quantity_rounds = 0
                    print(f"\rLucro atual: {self.profit}\r")
                    print(f"\rSaldo atual: {self.cycle_balance}\n")
            elif self.awaiting_status("rolling"):
                # print(f"\rStatus: Rolling {get_timer()}", end="")
                with yaspin(Spinners.earth, text="Girando...") as sp:
                    await asyncio.sleep(1.5)
            elif self.awaiting_status("complete"):
                # print(f"\rStatus: Complete {get_timer()}", end="")
                with yaspin(Spinners.hearts, text="Completo") as sp:
                    await asyncio.sleep(1.5)
                if preview_roulette:
                    self.last_doubles = self.get_doubles()
                    self.preview(end="\n")
            if self.client.websocket_closed:
                self.client.start_websocket()
            await asyncio.sleep(1)

    async def double_bets(self, current_amount: float) -> Dict:
        print(f"\nSaldo antes de apostar: {self.cycle_balance}")
        result_bet = {}
        result_dict = {
            "object": {}
        }
        current_balance = self.current_balance
        print(f"Aposta de {float(current_amount):.2f} R$ feita no Branco às {get_timer()}\r")
        current_balance -= current_amount
        self.cycle_balance -= current_amount
        if not is_demo:
            self.client.double_bets("branco", current_amount)
        await self.wait_result("branco", result_bet)
        print(f'\nBranco: {"GREEN" if result_bet["object"]["win"] else "LOSS"} | HORÁRIO: {get_timer()}\r')
        if result_bet["object"]["win"]:
            result_dict["object"]["win"] = True
            current_balance += current_amount * 14
            self.cycle_balance += current_amount * 14
        else:
            result_dict["object"]["win"] = False
        self.cycle_balance = truncate(float(self.cycle_balance), 2)
        result_dict["object"]["balance"] = truncate(current_balance, 2)
        result_dict["object"]["profit"] = self.calculate_profit()
        result_dict["object"]["created"] = get_timer()
        return result_dict

    async def wait_result(self, color: str, bet: dict) -> Dict:
        win = await self.client.awaiting_double()
        result_dict = {
            "result": False,
        }
        roll_win = win["roll"]
        result_dict["roll"] = roll_win
        color_win = self.get_color(win["color"])
        result_dict["color"] = color_win
        if color_win == color:
            result_dict["result"] = True
            result_dict["win"] = True
        else:
            result_dict["win"] = False
        bet["object"] = result_dict
        return result_dict

    def awaiting_status(self, status: str) -> bool:
        if self.client.get_status() == status:
            return True

    def get_doubles(self) -> List:
        doubles = self.client.get_last_doubles()
        if doubles:
            return [[item["value"], item["color"]] for item in doubles["items"]][::-1]
        return []

    def preview(self, end="") -> None:
        self.last_doubles = self.last_doubles[1:]
        colored_string = ', '.join([
            f"\033[10;40m {item[0]} \033[m" if item[1] == "preto"
            else f"\033[10;41m {item[0]} \033[m" if item[1] == "vermelho"
            else f"\033[10;47m {item[0]} \033[m" for item in self.last_doubles])
        print(f"\rÚltimos giros >>> {colored_string}", end)

    def get_color(self, number: int) -> str:
        return self.colors.get(number, )

    def calculate_profit(self):
        return truncate(self.cycle_balance - self.first_balance, 2)

    def calculate_enter(self):
        return truncate(abs((self.meta - self.current_balance) / 13), 2)


async def main():
    roulette = Roulette()
    await roulette.run()


def handler(signum, frame):
    res = input("\rVocê realmente quer sair? y/n ")
    if res == 'y':
        exit(0)


if __name__ == "__main__":
    os.system('color 0f') if os.name == 'nt' else None
    warnings.filterwarnings("ignore")
    signal.signal(signal.SIGINT, handler)
    print("\rAguardando horário de entrada...\n")

try:
    asyncio.run(main())
except KeyboardInterrupt as e:
    print("\nFechando...")
    quit(0)
