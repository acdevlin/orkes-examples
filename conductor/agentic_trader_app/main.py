import json
import logging
import os
import time

from conductor.client.automator.task_handler import TaskHandler
from conductor.client.configuration.configuration import Configuration
from conductor.client.http.models import StartWorkflowRequest
from conductor.client.metadata_client import MetadataClient
from conductor.client.orkes_clients import OrkesClients
from workers import *
from prompts import configure_integrations


def start_workers(api_config):
    task_handler = TaskHandler(
        workers=[],
        configuration=api_config,
        scan_for_annotated_workers=True,
    )
    task_handler.start_processes()
    return task_handler


def add_agentic_workflow(metadata_client: MetadataClient):
    with open('workflow.json', 'r') as file:
        data = json.load(file)
    return metadata_client.register_workflow_def(workflow_def=data, overwrite=True)


def main():
    api_config = Configuration()
    api_config.apply_logging_config(level=logging.INFO)
    clients = OrkesClients(configuration=api_config)
    workflow_client = clients.get_workflow_client()
    metadata_client = clients.get_metadata_client()

    task_handler = start_workers(api_config=api_config)

    # Only need to configure integrations once, since they are saved to your
    # Orkes account.
    #configure_integrations(api_config=api_config)
    add_agentic_workflow(metadata_client=metadata_client)

    request = StartWorkflowRequest(name='agentic_stock_trader_autonomous', version=1, input={
        'instructions': 'purchase 1 share of google'
    })

    try:
      workflow_id = workflow_client.start_workflow(start_workflow_request=request)
      workflow = workflow_client.get_workflow(workflow_id=workflow_id, include_tasks=False)
      print(f'track the agent execution here {os.getenv("CONDUCTOR_SERVER_URL")}/../execution/{workflow.workflow_id}')
      while workflow.is_running():
          print(f'{workflow.variables["instructions"]}')
          workflow = workflow_client.get_workflow(workflow_id=workflow_id, include_tasks=False)
          time.sleep(5)
    except Exception as e:
      print(f'Error starting workflow: {e}')
    print('Completed.  Did we make money?')
    task_handler.stop_processes()


if __name__ == '__main__':
    main()