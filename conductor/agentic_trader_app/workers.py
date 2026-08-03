import fcntl
import random
from typing import List

from conductor.client.worker.worker_task import worker_task
from config import ALL_PHRASES, BALANCE_FILE, LOG_FILE, MAX_QUANTITY, MIN_QUANTITY, STARTING_BALANCE

### BEGIN HELPER FUNCTIONS ###

def default_quantity() -> int:
  """
  Returns a random fallback share count when the LLM omits a quantity.
  """
  return random.randint(MIN_QUANTITY, MAX_QUANTITY)

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

def held_quantity(portfolio, ticker) -> int:
  """
  Returns the total shares held for `ticker` in the portfolio.
  """
  ticker = str(ticker).lower()
  total = 0
  for entry in portfolio or []:
    if isinstance(entry, dict):
      if str(entry.get('ticker', '')).lower() == ticker:
        total += int(entry.get('quantity', 0))
    elif str(entry).lower() == ticker:
      total += 1
  return total

def to_quantity(value, portfolio=None, ticker=None) -> int:
  """
  Normalizes an LLM-provided quantity into a concrete share count.

  Numeric values (ints, floats, or numeric strings) are used directly.
  "all"-phrases mean the whole held position when a portfolio is given (sells),
  otherwise a randomized default amount so buys vary in size. Anything else
  unparsable also falls back to a randomized default.
  """
  if isinstance(value, bool):
    return default_quantity()
  if isinstance(value, (int, float)):
    return max(int(value), 1)
  if isinstance(value, str):
    s = value.strip().lower()
    if s in ALL_PHRASES:
      return held_quantity(portfolio, ticker) or default_quantity()
    try:
      return max(int(float(s)), 1)
    except ValueError:
      return default_quantity()
  return default_quantity()

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


def init_balance(amount: float = STARTING_BALANCE):
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
    
### END HELPER FUNCTIONS ###
### BEGIN WORKER TASKS ###

@worker_task("get_stock_price")
def get_stock_price(ticker: str) -> float:
  """
  Returns a random mock quote for the given symbol.
  """
  return float(random.randrange(90, 120, 1))

@worker_task("buy_stock")
def buy_stock(ticker: str, quantity: int, price: float) -> str:
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
def sell_stock(ticker: str, quantity: int, price: float, portfolio: List[dict]) -> str:
  """
  Sells `quantity` shares of `ticker` at `price`, crediting the account.

  "all" sells the entire held position. Note: does not verify the ticker is
  actually held, so an over-zealous decider can sell repeatedly.
  """
  quantity = to_quantity(quantity, portfolio, ticker)
  price = to_price(price, ticker)
  log(f'Selling {quantity} shares of {ticker} at {price} each.')
  amount = price * quantity
  current_balance = read_balance()
  current_balance = current_balance + amount
  update_balance(current_balance)
  log(f'Sold {ticker} and we now have {current_balance}')
  return "OK"

@worker_task("update_portfolio")
def update_portfolio(ticker: str, quantity: int, price: float, portfolio: List[dict]) -> List[dict]:
  """
  Adds `quantity` shares of `ticker` bought at `price` to the portfolio.

  Tracks the weighted-average purchase price per share in `avg_price`, and
  returns the updated list of {ticker, quantity, avg_price} holdings.
  """
  quantity = to_quantity(quantity)
  ticker = str(ticker).lower()
  share_price = to_price(price, ticker)
  updated = []
  added = False
  for entry in portfolio or []:
    if isinstance(entry, dict):
      entry_ticker = str(entry.get('ticker', '')).lower()
      new_entry = dict(entry)
    else:
      entry_ticker = str(entry).lower()
      new_entry = {'ticker': entry, 'quantity': 0}
    if entry_ticker == ticker:
      held_shares = int(new_entry.get('quantity', 0))
      held_price = float(new_entry.get('avg_price', share_price))
      total_shares = held_shares + quantity
      new_entry['quantity'] = total_shares
      new_entry['avg_price'] = round((held_shares * held_price + quantity * share_price) / total_shares, 2)
      added = True
    updated.append(new_entry)
  if not added:
    updated.append({'ticker': ticker, 'quantity': quantity, 'avg_price': share_price})
  return updated

@worker_task("remove_from_portfolio")
def remove_from_portfolio(ticker: str, quantity: int, portfolio: List[dict]) -> List[dict]:
  """
  Sells `quantity` shares of `ticker` from the portfolio, dropping the
  entry when the position hits zero, and returns the updated holdings.

  Partial sells keep the tracked avg_price so the remaining shares retain
  their original cost basis.
  """
  quantity = to_quantity(quantity, portfolio, ticker)
  ticker = str(ticker).lower()
  out = []
  for entry in portfolio or []:
    if isinstance(entry, dict):
      name = str(entry.get('ticker', '')).lower()
      new_entry = dict(entry)
    else:
      name = str(entry).lower()
      new_entry = {'ticker': entry, 'quantity': 0}
    if name == ticker:
      new_entry['quantity'] = int(new_entry.get('quantity', 0)) - quantity
      if new_entry['quantity'] <= 0:
        continue
    out.append(new_entry)
  return out


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

### END WORKER TASKS ###