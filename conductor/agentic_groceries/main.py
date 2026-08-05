from conductor.ai.agents.runtime.config import AgentConfig
from conductor.ai.agents import AgentRuntime
from conductor.client.configuration.configuration import Configuration
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient
from conductor.client.orkes_clients import OrkesClients

from settings import (
  CONDUCTOR_AUTH_SECRET, 
  POLL_INTERVAL_MS, 
  SERVER_URL, 
  CONDUCTOR_AUTH_KEY,
  WORKFLOW_FILE
)
from shopping_list_agent import create_shopping_list_agent

import argparse
import json

# Required import to avoid pickling error from @tool in the current SDK.
# Should be resolved with this pull: https://github.com/conductor-oss/python-sdk/pull/414
import multiprocessing
multiprocessing.set_start_method("fork", force=True)


def upload_meal_planner_workflow(api_config):
  """Registers the "Meal And Grocery Planner" as a Workflow on Orkes.

  Args:
      api_config: Conductor API client configuration.

  Returns:
      None.
  """
  with open(WORKFLOW_FILE, "r") as file:
    data = json.load(file)
  metadata_client = OrkesClients(configuration=api_config).get_metadata_client()
  metadata_client.register_workflow_def(workflow_def=data, overwrite=True)


def main():
  parser = argparse.ArgumentParser(
      description="""
        Run the meal and grocery planner agentic workflow.
        Default: deploy all artifacts to Orkes Conductor, run the workflow locally once, then exit. 
      """
  )
  parser.add_argument(
      "--server",
      action="store_true",
      default=False,
      help="Serve to Orkes Conductor and keep a long-lived worker polling for tool tasks.",
  )
  parser.add_argument(
    "--deploy-only",
    action="store_true",
    default=False,
    help="Deploy all artifacts to Orkes Conductor, then exit without running the workflow.",
  )
  args = parser.parse_args()

  api_config = Configuration(server_api_url=SERVER_URL)
  # Keep our Conductor workflow updated in Orkes
  upload_meal_planner_workflow(api_config)
  # Ensure the shopping list prompt template exists on the server
  prompt_client = OrkesPromptClient(configuration=api_config)

  # Point the runtime at Orkes Conductor instead of the default localhost.
  runtime = AgentRuntime(
      config=AgentConfig(
          server_url=SERVER_URL,
          auth_key=CONDUCTOR_AUTH_KEY,
          auth_secret=CONDUCTOR_AUTH_SECRET,
          worker_poll_interval_ms=POLL_INTERVAL_MS,
      )
  )

  with runtime:
      shopping_list_agent = create_shopping_list_agent(prompt_client)
      runtime.deploy(shopping_list_agent)
      print("Deployment complete.")
      if args.deploy_only:
          print("Exiting after deployment, as requested.")
      elif args.server:
          print("Serving to Orkes Conductor. Press Ctrl+C to exit.")
          runtime.serve(shopping_list_agent)
      else:
          print("Running the workflow once locally.")
          result = runtime.run(
              shopping_list_agent,
              ("Add a gallon of milk, a dozen eggs, and a loaf of bread to my shopping list. "
               "Then show me the list.",),
          )
          result.print_result()

if __name__ == "__main__":
  main()  
