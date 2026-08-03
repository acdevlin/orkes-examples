import argparse
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
from config import LOG_FILE, STARTING_BALANCE, WORKFLOW_FILE, WORKFLOW_NAME, WORKFLOW_VERSION, WORKFLOW_INPUT_INSTRUCTIONS

### BEGIN HELPER FUNCTIONS ###

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
  with open(WORKFLOW_FILE, 'r') as file:
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


def parse_args():
  """
  Parses CLI arguments for the trader app.
  """
  parser = argparse.ArgumentParser()
  parser.add_argument('--verbose', action='store_true', default=False,
                      help='Print the detailed workflow instructions executed during the run')
  return parser.parse_args()


def build_api_config():
  """
  Creates and configures the Conductor API client configuration.
  """
  api_config = Configuration()
  api_config.apply_logging_config(level=logging.INFO)
  return api_config

def create_clients(api_config):
  """
  Creates the workflow and metadata clients used by the app.
  """
  clients = OrkesClients(configuration=api_config)
  return clients.get_workflow_client(), clients.get_metadata_client()

def register_signal_handlers(task_handler):
  """
  Registers graceful shutdown handlers for the worker processes.
  """
  for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(sig, lambda s, f: stop_handler(task_handler, s, f))

def build_start_workflow_request():
  """
  Builds the workflow start request used for the trader run.
  """
  return StartWorkflowRequest(name=WORKFLOW_NAME, version=WORKFLOW_VERSION, input={
      'instructions': WORKFLOW_INPUT_INSTRUCTIONS
  })

def run_workflow(workflow_client, request):
  """
  Starts the workflow, polls it until completion, and collects instructions.
  """
  workflow = None
  seen = set()
  offset = 0
  wf_instructions = []

  try:
    workflow_id = workflow_client.start_workflow(start_workflow_request=request)
    workflow = workflow_client.get_workflow(workflow_id=workflow_id, include_tasks=True)
    print(f'track the agent execution here {os.getenv("CONDUCTOR_SERVER_URL")}/../execution/{workflow.workflow_id}')
    while workflow.is_running():
      offset = drain_log(offset)
      print_new_plans(workflow, seen)
      print_new_actions(workflow, seen)
      workflow = workflow_client.get_workflow(workflow_id=workflow_id, include_tasks=True)
      instructions = workflow.variables.get('instructions') if workflow and workflow.variables else None
      if instructions is not None:
        wf_instructions.append(instructions)
      time.sleep(5)
    offset = drain_log(offset)
  except Exception as e:
    print(f'Error starting workflow: {e}')
    
  return workflow, wf_instructions


def initialize_runtime(api_config, metadata_client):
  """
  Initializes the runtime state for a trader run.
  """
  init_balance(amount=STARTING_BALANCE)
  clear_log()
  task_handler = start_workers(api_config=api_config)
  register_signal_handlers(task_handler)

  # Re-saves the prompt templates to the Orkes account each run so prompt
  # changes in prompts.py take effect. This is idempotent.
  configure_integrations(api_config=api_config)
  add_agentic_workflow(metadata_client=metadata_client)
  return task_handler

def print_final_summary(starting_balance, holdings, wf_instructions, verbose):
  """
  Prints the final balance, portfolio summary, and optionally the workflow instructions.
  """
  final_balance = read_balance()
  change = final_balance - starting_balance

  print('Completed.')
  print(f'Starting balance: ${starting_balance:.2f}')
  print(f'Final balance: ${final_balance:.2f}')
  print(f'Net cash gain/loss: ${change:.2f}')
  print_holdings_summary(holdings)

  if verbose:
    print('='*50 + '\n\n')
    print('Workflow executed the following instructions:')
    for i, instruction in enumerate(wf_instructions):
      print(f'Iteration {i+1}: {instruction}')
      print('-'*50)

### END HELPER FUNCTIONS ###

def main():
  """
  Runs the agentic stock trader end to end.

  Resets the account, starts the workers, re-saves the prompts, registers the
  workflow, and starts it, polling until the workflow finishes.
  """
  args = parse_args()

  api_config = build_api_config()
  workflow_client, metadata_client = create_clients(api_config)

  task_handler = initialize_runtime(api_config, metadata_client)

  request = build_start_workflow_request()
  workflow, wf_instructions = run_workflow(workflow_client, request)

  holdings = workflow.variables.get('portfolio', []) if workflow else []
  print_final_summary(STARTING_BALANCE, holdings, wf_instructions, args.verbose)

  task_handler.stop_processes()


if __name__ == '__main__':
  main()