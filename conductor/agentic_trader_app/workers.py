import fcntl
import os
import random
from typing import List

from conductor.client.worker.worker_task import worker_task

# Balance is shared across worker processes via a file on disk. Each read/write
# takes an advisory file lock so concurrent trades can't race each other.
BALANCE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'balance.dat')


def log(msg):
    # Piped/buffered output can raise OSError on flush; swallow it so worker
    # processes don't crash just because the console is a pipe.
    try:
        print(msg)
    except OSError:
        pass


def init_balance(amount=2000.0):
    # Resets the account to a known starting amount before each run.
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
    # Mock price feed: returns a random quote per symbol.
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
    # Credits proceeds to the balance. Note: does not verify the ticker is
    # actually held, so an over-zealous decider can sell repeatedly.
    amount = price * quantity
    current_balance = read_balance()
    current_balance = current_balance + amount
    update_balance(current_balance)
    log(f'Sold {ticker} and we now have {current_balance}')
    return "OK"


@worker_task("remove_from_portfolio")
def remove_from_portfolio(ticker: str, portfolio: List[str]) -> List[str]:
    # Case-insensitive filter that drops the sold ticker from the portfolio.
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
