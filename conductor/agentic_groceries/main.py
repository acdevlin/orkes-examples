from conductor.ai.agents.runtime.config import AgentConfig
from conductor.ai.agents import AgentRuntime
from conductor.client.configuration.configuration import Configuration
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient

from settings import CONDUCTOR_AUTH_SECRET, POLL_INTERVAL_MS, SERVER_URL, CONDUCTOR_AUTH_KEY
from shopping_list_agent import create_shopping_list_agent

import argparse

# Required import to avoid pickling error from @tool in the current SDK.
# Should be resolved with this pull: https://github.com/conductor-oss/python-sdk/pull/414
import multiprocessing
multiprocessing.set_start_method("fork", force=True)


def main():
  parser = argparse.ArgumentParser(
      description="Run the shopping list agent. "
      "Default: deploy and run a single prompt locally, then exit. "
      "Use --server to deploy and keep a long-lived worker polling for tool tasks."
  )
  parser.add_argument(
      "--server",
      action="store_true",
      default=False,
      help="Deploy the agent and keep a long-lived worker polling for tool tasks.",
  )
  args = parser.parse_args()

  api_config = Configuration(server_api_url=SERVER_URL)
  # Ensure the shopping list prompt template exists on the server
  prompt_client = OrkesPromptClient(configuration=api_config)

  # AgentRuntime() reads AGENTSPAN_* env vars (default localhost), NOT the
  # CONDUCTOR_* vars. Point it at the Orkes account so deploy() reaches the
  # server, and use auth_key/auth_secret so a JWT is minted for X-Authorization.
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
      if args.server:
          runtime.serve(shopping_list_agent)
      else:
          result = runtime.run(
              shopping_list_agent,
              ("Add a gallon of milk, a dozen eggs, and a loaf of bread to my shopping list. "
               "Then show me the list.",),
          )
          result.print_result()

if __name__ == "__main__":
  main()  
