import fcntl
import os
import random
from typing import List

from conductor.client.worker.worker_task import worker_task

# Balance is shared across worker processes via a file on disk. Each read/write
# takes an advisory file lock so concurrent trades can't race each other.
BALANCE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'balance.dat')

# Workers run in separate processes, so they can't safely write to the main
# process's stdout. Instead they append log lines here (flock-serialized) and
# main.py drains and prints them in order.
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'actions.log')


def log(msg):
    """
    Appends a line to the shared worker log file.
    """
    with open(LOG_FILE, 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(msg + '\n')


def clear_log():
    """
    Truncates the shared log so a fresh run starts with an empty log.
    """
    with open(LOG_FILE, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)


def to_quantity(value) -> int:
    """
    Normalizes an LLM-provided quantity into a share count.

    The LLM may emit quantity as an int, a numeric string ("1"), or a phrase
    like "all". The portfolio only tracks ticker names (not per-share counts),
    so "all" is treated as a single share.
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ('', 'all', 'everything', 'all shares'):
            return 1
        try:
            return int(float(s))
        except ValueError:
            return 1
    return 1


def to_price(value, ticker) -> float:
    """
    Normalizes an LLM-provided price into a float.

    Falls back to a mock quote when the value is missing or not a number, since
    the executor sometimes omits the price field entirely.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return get_stock_price(ticker)
    return get_stock_price(ticker)


def init_balance(amount: float = 2000.0):
    """
    Resets the account to a known starting amount before each run.
    """
    with open(BALANCE_FILE, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(str(amount))


def read_balance() -> float:
    """
    Returns the current account balance from the shared balance file.
    """
    with open(BALANCE_FILE, 'r') as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        return float(f.read())


def update_balance(amount: float):
    """
    Overwrites the shared balance file with the given amount.
    """
    with open(BALANCE_FILE, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        f.truncate()
        f.write(str(amount))


@worker_task("get_stock_price")
def get_stock_price(ticker: str) -> float:
    """
    Returns a random mock quote for the given symbol.
    """
    return float(random.randrange(90, 120, 1))


@worker_task("buy_stock")
def buy_stock(ticker: str, quantity, price) -> str:
    """
    Buys `quantity` shares of `ticker` at `price` from the account balance.

    Returns "OK" on success, or an error message when funds are insufficient.
    """
    quantity = to_quantity(quantity)
    price = to_price(price, ticker)
    log(f'Buying {quantity} shares of {ticker} at {price} each.')
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
def sell_stock(ticker: str, quantity, price) -> str:
    """
    Sells `quantity` shares of `ticker` at `price`, crediting the account.

    Note: does not verify the ticker is actually held, so an over-zealous
    decider can sell repeatedly.
    """
    quantity = to_quantity(quantity)
    price = to_price(price, ticker)
    log(f'Selling {quantity} shares of {ticker} at {price} each.')
    amount = price * quantity
    current_balance = read_balance()
    current_balance = current_balance + amount
    update_balance(current_balance)
    log(f'Sold {ticker} and we now have {current_balance}')
    return "OK"


@worker_task("remove_from_portfolio")
def remove_from_portfolio(ticker: str, portfolio: List[str]) -> List[str]:
    """
    Returns the portfolio with the given ticker removed (case-insensitive).
    """
    t = str(ticker).lower()
    return [s for s in (portfolio or []) if str(s).lower() != t]


@worker_task("check_account_balance")
def check_account_balance() -> float:
    """
    Returns the current account balance.
    """
    return read_balance()


@worker_task("transfer_money")
def transfer_money(amount: float) -> float:
    """
    Adds `amount` to the account balance and returns the new balance.
    """
    current_balance = read_balance()
    current_balance = current_balance + amount
    update_balance(current_balance)
    return current_balance
