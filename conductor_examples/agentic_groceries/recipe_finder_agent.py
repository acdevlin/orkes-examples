from typing import Optional

from conductor.ai.agents import Agent, tool
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient

from bbc_recipe_scraper import scrape_recipes as scrape_bbc_recipes
from prompts import (
  RECIPE_FINDER_PROMPT_TEXT,
  RECIPE_FINDER_PROMPT_NAME,
  RECIPE_FINDER_PROMPT_DESCRIPTION
)
from settings import (
  SDK_MODEL,
  MAX_TURNS,
  SERVER_MODELS
)
from shared_utils import ensure_prompt

@tool
def find_recipes(preferences: Optional[str] = None, recipe_count: int = 10) -> dict:
  """Find recipes based on provided dietary preference, palate, or other requirements.

  Args:
    preferences: Dietary preference (eg: "vegetarian") used to filter the results.
    recipe_count: Number of recipes to fetch.

  Returns:
    Dictionary with a list of recipes.
  """
  return {"recipes": scrape_bbc_recipes(preferences, recipe_count)}


def create_recipe_finder_agent(prompt_client: OrkesPromptClient) -> Agent:
  """Creates an agent for finding recipes based on dietary preferences, palate,
  or other specific requirements.

  Args:
    prompt_client: An instance of OrkesPromptClient to manage prompts.

  Returns:
    An instance of Agent configured for recipe finding.
  """
  # Ensure the prompt is registered with the Orkes Prompt Client
  prompt = ensure_prompt(
    prompt_client,
    RECIPE_FINDER_PROMPT_NAME,
    RECIPE_FINDER_PROMPT_DESCRIPTION,
    RECIPE_FINDER_PROMPT_TEXT,
    SERVER_MODELS,
  )
  instructions = prompt.template or RECIPE_FINDER_PROMPT_TEXT
  # Create and return the agent
  return Agent(
    name="recipe_finder_agent",
    model=SDK_MODEL,
    instructions=instructions,
    tools=[find_recipes],
    max_turns=MAX_TURNS,
  )
