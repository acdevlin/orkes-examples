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
from recipe_finder_agent import create_recipe_finder_agent, find_recipes
from menu_planner_agent import create_menu_planner_agent
import recipe_extractor   # noqa: F401  (registers the extract_recipes worker via @worker_task)

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
    # Create the agents
    recipe_finder_agent = create_recipe_finder_agent(prompt_client)
    menu_planner_agent = create_menu_planner_agent(prompt_client)
    shopping_list_agent = create_shopping_list_agent(prompt_client)
    # Deploy the agents to Orkes Conductor
    runtime.deploy(recipe_finder_agent)
    runtime.deploy(menu_planner_agent)
    runtime.deploy(shopping_list_agent)
    print("Deployment complete.")
    
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
