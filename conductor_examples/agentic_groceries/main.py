import argparse
import json

# Required import to avoid pickling error from @tool in the current SDK.
# Should be resolved with this pull: https://github.com/conductor-oss/python-sdk/pull/414
import multiprocessing

import conductor.ai.agents.runtime.runtime as runtime_module

from conductor.ai.agents import AgentRuntime
from conductor.ai.agents.runtime.config import AgentConfig
from conductor.client.configuration.configuration import Configuration
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient
from conductor.client.orkes_clients import OrkesClients

from menu_planner_agent import create_menu_planner_agent
from menu_plan_formatter import ensure_format_menu_plan_worker
from recipe_extractor import ensure_extract_recipes_worker
from recipe_finder_agent import create_recipe_finder_agent, find_recipes
from settings import POLL_INTERVAL_MS, SERVER_URL, WORKFLOW_FILE
from shared_utils import patch_workflow_prompts
from shopping_list_agent import create_shopping_list_agent


def relax_tool_response_timeouts():
  """Loosen the SDK's default worker response timeout for tool tasks.

  The SDK's ``_default_task_def`` uses a 10s response_timeout_seconds. The
  shopping list agent fires many parallel ``add_item`` tool calls in a single
  turn (26 in the failing run). With the worker manager's default 10 threads,
  queued tasks can sit past the 10s window and get marked ``TIMED_OUT``,
  retried, and stall the agent. Override the default to a generous 120s;
  lease-extend heartbeats keep long-running tasks alive.
  """
  original = runtime_module._default_task_def

  def patched(name, **kwargs):
    kwargs.setdefault("response_timeout_seconds", 120)
    return original(name, **kwargs)

  runtime_module._default_task_def = patched


def upload_meal_planner_workflow(api_config):
  """Registers the "Meal And Grocery Planner" as a Workflow on Orkes.

  Args:
    api_config: Conductor API client configuration.

  Returns:
    None.
  """
  with open(WORKFLOW_FILE, "r") as file:
    data = json.load(file)
  # Keep the workflow's embedded agent prompts in sync with prompts.py.
  patch_workflow_prompts(data)
  metadata_client = OrkesClients(configuration=api_config).get_metadata_client()
  metadata_client.register_workflow_def(workflow_def=data, overwrite=True)


def main():
  """Deploy all artifacts to Orkes Conductor, then either serve workers,
  run the workflow locally once, or exit after deployment.

  Returns:
    None.
  """
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

  # Relax the SDK's 10s tool worker response timeout before anything is
  # deployed/served, so parallel add_item calls have room to complete.
  relax_tool_response_timeouts()

  api_config = Configuration(server_api_url=SERVER_URL)
  # Keep our Conductor workflow updated in Orkes
  upload_meal_planner_workflow(api_config)
  # Ensure the shopping list prompt template exists on the server
  prompt_client = OrkesPromptClient(configuration=api_config)

  # Point the runtime at Orkes Conductor instead of the default localhost.
  runtime = AgentRuntime(
      configuration=api_config,
      settings=AgentConfig(
          worker_poll_interval_ms=POLL_INTERVAL_MS,
      )
  )

  with runtime:
    # Create the agents
    recipe_finder_agent = create_recipe_finder_agent(prompt_client)
    menu_planner_agent = create_menu_planner_agent(prompt_client)
    shopping_list_agent = create_shopping_list_agent(prompt_client)
    # Deploy the agents to Orkes Conductor
    runtime.deploy(recipe_finder_agent)
    runtime.deploy(menu_planner_agent)
    runtime.deploy(shopping_list_agent)
    print("Deployment complete.")

    # Register the SIMPLE workers so the workflow's extract_recipes and
    # format_menu_plan tasks are polled while serving. The @worker_task
    # decorators register them at import time; these calls make that
    # dependency explicit.
    ensure_extract_recipes_worker()
    ensure_format_menu_plan_worker()

    if args.deploy_only:
        print("Exiting after deployment, as requested.")
    elif args.server:
        print("Serving to Orkes Conductor. Press Ctrl+C to exit.")
        runtime.serve(recipe_finder_agent, menu_planner_agent, shopping_list_agent)
    else:
        print("Running the workflow once locally.")

        # Find recipes based on user input.
        recipe_finder_result = runtime.run(
            recipe_finder_agent,
            ("Find me some vegetarian recipes.",),
        )
        print("\n\nRecipe Finder Result:")
        recipe_finder_result.print_result()

        # Read the recipes the recipe finder selected from its tool output.
        recipes = []
        for call in recipe_finder_result.tool_calls:
          result = call.get("result") or {}
          if isinstance(result, dict) and isinstance(result.get("result"), dict):
            result = result["result"]
          if isinstance(result, dict) and result.get("recipes"):
            recipes = result["recipes"]
            break
        if not recipes:
          print("No suitable recipes found. Exiting.")
          return
        recipes_text = json.dumps(recipes, indent=2)

        # Use the JSONified recipes to generate a weekly menu plan for 2 people.
        menu_planner_result = runtime.run(
            menu_planner_agent,
            (f"Plan dinners for 2 people for the next 7 days "
             f"using only these recipes:\n{recipes_text}",),
        )
        print("\n\nMenu Planner Result:")
        menu_planner_result.print_result()

        # In a real workflow run, there should be a human appoval for the meal plan
        # before generating the final shopping list of all ingredients.

        # Read the required ingredients straight from the menu plan tool output.
        menu_ingredients = []
        for call in menu_planner_result.tool_calls:
          plan = call.get("result") or {}
          if isinstance(plan, dict) and isinstance(plan.get("result"), dict):
            plan = plan["result"]
          if isinstance(plan, dict) and plan.get("required_ingredients"):
            menu_ingredients = plan["required_ingredients"]
            break
        if menu_ingredients:
          ingredients_text = "\n".join(f"- {ingredient}" for ingredient in menu_ingredients)
          shopping_prompt = (
            f"Add the following required ingredients to my shopping list:\n{ingredients_text}\n"
            "Then show me the list."
          )
        else:
          # Fallback if we didn't find any ingredients in the menu plan output.
          shopping_prompt = (
            "Add a gallon of milk, a dozen eggs, and a loaf of bread to my shopping list. "
            "Then show me the list."
          )

        # Generate the final shopping list.
        shopping_list_result = runtime.run(
            shopping_list_agent,
            (shopping_prompt,),
        )
        print("\n\nShopping List Result:")
        shopping_list_result.print_result()


if __name__ == "__main__":
  main()
