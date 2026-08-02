import json5
import logging
import os
import signal
import sys
import time

from conductor.client.automator.task_handler import TaskHandler
from conductor.client.configuration.configuration import Configuration
from conductor.client.http.models import StartWorkflowRequest
from conductor.client.metadata_client import MetadataClient
from conductor.client.orkes_clients import OrkesClients
from workers import *
from prompts import configure_integrations

# The account is reset to this amount at the start of every run.
STARTING_BALANCE = 20000.0


def start_workers(api_config):
  """
  Spawns one poller process per @worker_task function in workers.py.
  """
  task_handler = TaskHandler(
      workers=[],
      configuration=api_config,
      scan_for_annotated_workers=True,
  )
  task_handler.start_processes()
  return task_handler


def add_agentic_workflow(metadata_client: MetadataClient):
  """
  Registers workflow.jsonc as the agentic stock trader workflow.

  workflow.jsonc carries // comments and trailing commas, so it's parsed with
  json5 rather than the strict standard-library json parser.
  """
  with open('workflow.jsonc', 'r') as file:
    data = json5.loads(file.read())
  return metadata_client.register_workflow_def(workflow_def=data, overwrite=True)


def print_new_actions(workflow, seen):
  """
  Prints each executor decision exactly once (deduped by task id) as the
  workflow runs, so the console shows what actually executed rather than
  just the decider's plan.

  Both the executor and decider run once per loop iteration, so these lines
  line up with the worker balance logs.
  """
  for task in workflow.tasks or []:
    if not task.task_id or task.task_id in seen or task.reference_task_name != 'llm_chat_complete_ref':
      continue
    seen.add(task.task_id)
    res = (task.output_data or {}).get('result') or {}
    cmd = res.get('command')
    if not cmd:
      continue
    param = res.get('param') or {}
    detail = ' '.join(f'{k}={v}' for k, v in param.items())
    print(f'  Executed [iteration {task.iteration}]: {cmd} {detail}'.rstrip())


def print_new_plans(workflow, seen):
  """
  Prints the decider's plan for each loop iteration exactly once.

  The plan is produced by the next_action_ref LLM at the end of an iteration
  and feeds the executor at the start of the next one, so printing both with
  their iteration numbers makes the flow explicit.
  """
  for task in workflow.tasks or []:
    if not task.task_id or task.task_id in seen or task.reference_task_name != 'next_action_ref':
      continue
    seen.add(task.task_id)
    plan = (task.output_data or {}).get('result')
    if not plan:
      continue
    plan = ' '.join(str(plan).split())
    print(f'  Plan [iteration {task.iteration}]: {plan}')


def drain_log(offset):
  """
  Prints any worker log lines appended since the last poll.

  Workers write to a shared file (not stdout) because they run in separate
  processes; draining here keeps the console output in a single,
  deterministic stream.
  """
  with open(LOG_FILE, 'r') as f:
    f.seek(offset)
    data = f.read()
  if data:
    print(data, end='', flush=True)
  return offset + len(data)


def print_holdings_summary(holdings):
  """
  Prints each holding's share count, current quote, purchase value, market
  value, and gain/loss, plus the summed totals across the whole portfolio.
  """
  total_cost = 0.0
  total_value = 0.0
  print(f'Stock holdings:')
  if holdings:
    for h in holdings:
      if isinstance(h, dict):
        ticker = h.get('ticker')
        quantity = int(h.get('quantity', 0))
        price = get_stock_price(ticker)
        value = quantity * price
        total_value += value
        avg_price = h.get('avg_price')
        if avg_price is None:
          print(f'  {ticker}: {quantity} share(s) @ ${price:.2f} | value ${value:.2f}')
        else:
          cost = quantity * float(avg_price)
          total_cost += cost
          diff = value - cost
          sign = '+' if diff >= 0 else '-'
          print(f'  {ticker}: {quantity} share(s) @ ${price:.2f} | bought ${cost:.2f}, '
                f'now ${value:.2f} ({sign}${abs(diff):.2f})')
      else:
        ticker = h
        price = get_stock_price(ticker)
        total_value += price
        print(f'  {ticker}: 1 share(s) @ ${price:.2f} | value ${price:.2f}')
  else:
    print('  none')
  total_gain = total_value - total_cost
  print(f'Total purchase value: ${total_cost:.2f}')
  print(f'Total market value: ${total_value:.2f}')
  print(f'Portfolio gain/loss: ${total_gain:.2f}')


def stop_handler(task_handler, signum, frame):
  """
  Stops child worker processes gracefully when the main process is terminated.
  """
  task_handler.stop_processes()
  sys.exit(0)


def main():
  """
  Runs the agentic stock trader end to end.

  Resets the account, starts the workers, re-saves the prompts, registers the
  workflow, and starts it, polling until the workflow finishes.
  """
  api_config = Configuration()
  api_config.apply_logging_config(level=logging.INFO)
  clients = OrkesClients(configuration=api_config)
  workflow_client = clients.get_workflow_client()
  metadata_client = clients.get_metadata_client()

  init_balance(amount=STARTING_BALANCE)
  clear_log()
  task_handler = start_workers(api_config=api_config)

  # Kills child processes gracefully regardless of how script is terminated
  for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(sig, lambda s, f: stop_handler(task_handler, s, f))

  # Re-saves the prompt templates to the Orkes account each run so prompt
  # changes in prompts.py take effect. This is idempotent.
  configure_integrations(api_config=api_config)
  add_agentic_workflow(metadata_client=metadata_client)

  request = StartWorkflowRequest(name='agentic_stock_trader_autonomous', version=1, input={
      'instructions': 'purchase 22 shares of NVIDIA stock (NVDA)'
  })

  workflow = None
  seen = set()
  offset = 0
  wf_instructions = []
    
  try:
    workflow_id = workflow_client.start_workflow(start_workflow_request=request)
    workflow = workflow_client.get_workflow(workflow_id=workflow_id, include_tasks=True)
    print(f'track the agent execution here {os.getenv("CONDUCTOR_SERVER_URL")}/../execution/{workflow.workflow_id}')
    while workflow.is_running():
      # The decider's plan and the executor's action are both tagged with
      # their loop iteration, so the output reads as a clear timeline even
      # though the workflow iterates faster than the 5s poll interval.
      offset = drain_log(offset)
      print_new_plans(workflow, seen)
      print_new_actions(workflow, seen)
      workflow = workflow_client.get_workflow(workflow_id=workflow_id, include_tasks=True)
      wf_instructions.append(workflow.variables["instructions"])
      time.sleep(5)
    offset = drain_log(offset)
  except Exception as e:
    print(f'Error starting workflow: {e}')
      
  holdings = workflow.variables.get('portfolio', []) if workflow else []
  final_balance = read_balance()
  change = final_balance - STARTING_BALANCE
    
  # Final output summary of the run.
  print('Completed.')
  print(f'Starting balance: ${STARTING_BALANCE:.2f}')
  print(f'Final balance: ${final_balance:.2f}')
  print(f'Net cash gain/loss: ${change:.2f}')
  print_holdings_summary(holdings)
  # Uncomment this to see the detailed instructions executed by the workflow.
  # Useful for debugging, but too verbose for normal runs.
  """
  print('='*50 + '\n\n')
  print('Workflow executed the following instructions:')
  for i, instruction in enumerate(wf_instructions):
      print(f'Iteration {i+1}: {instruction}')
      print('-'*50)
  """
    
  task_handler.stop_processes()


if __name__ == '__main__':
  main()