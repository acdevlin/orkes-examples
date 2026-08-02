import fcntl
import os
import random
from typing import List

from conductor.client.worker.worker_task import worker_task

BALANCE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'balance.dat')


def log(msg):
    try:
        print(msg)
    except OSError:
        pass


def init_balance(amount=2000.0):
    with open(BALANCE_FILE, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(str(amount))


def read_balance():
    with open(BALANCE_FILE, 'r') as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        return float(f.read())


def update_balance(amount):
    with open(BALANCE_FILE, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        f.truncate()
        f.write(str(amount))


@worker_task("get_stock_price")
def get_stock_price(ticker: str) -> float:
    return random.randrange(90, 120, 1)


@worker_task("buy_stock")
def buy_stock(ticker: str, quantity: int, price: float) -> str:
    cost = price * quantity
    current_balance = read_balance()
    if cost > current_balance:
      error_msg = f"Insufficient funds to buy {ticker} - requires {cost}, but only have {current_balance}"
      log(error_msg)
      return error_msg
    current_balance = current_balance - cost
    update_balance(current_balance)
    log(f'Bought {ticker} and we now have {current_balance}')
    return "OK"


@worker_task("sell_stock")
def sell_stock(ticker: str, quantity: int, price: float) -> str:
    amount = price * quantity
    current_balance = read_balance()
    current_balance = current_balance + amount
    update_balance(current_balance)
    log(f'Sold {ticker} and we now have {current_balance}')
    return "OK"


@worker_task("remove_from_portfolio")
def remove_from_portfolio(ticker: str, portfolio: List[str]) -> List[str]:
    t = str(ticker).lower()
    return [s for s in (portfolio or []) if str(s).lower() != t]


@worker_task("check_account_balance")
def check_account_balance() -> float:
    return read_balance()


@worker_task("transfer_money")
def transfer_money(amount: float) -> float:
    current_balance = read_balance()
    current_balance = current_balance + amount
    update_balance(current_balance)
    return current_balance
