from typing import Optional

from conductor.ai.agents import Agent, tool
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient

from bbc_recipe_scraper import scrape_recipes as scrape_bbc_recipes
from thymeout_recipe_scraper import scrape_recipes as scrape_thymeout_recipes
from prompts import (
  RECIPE_FINDER_BBC_PROMPT_TEXT,
  RECIPE_FINDER_BBC_PROMPT_NAME,
  RECIPE_FINDER_BBC_PROMPT_DESCRIPTION,
  RECIPE_FINDER_THYMEOUT_PROMPT_TEXT,
  RECIPE_FINDER_THYMEOUT_PROMPT_NAME,
  RECIPE_FINDER_THYMEOUT_PROMPT_DESCRIPTION,
)
from settings import (
  SDK_MODEL,
  MAX_TURNS,
  SERVER_MODELS
)
from shared_utils import ensure_prompt


@tool
def find_bbc_recipes(preferences: Optional[str] = None, recipe_count: int = 10) -> dict:
  """Find recipes on BBC Food based on provided dietary preference, palate, or other requirements.

  Scrapes live recipes from BBC Food matching the preferences. When the
  preferences imply a vegetarian or vegan diet, only recipes verified as
  such by the source are returned.

  Args:
    preferences: Dietary preference (eg: "vegetarian") used to filter the results.
    recipe_count: Number of recipes to fetch.

  Returns:
    Dictionary with a list of recipes.
  """
  return {"recipes": scrape_bbc_recipes(preferences, recipe_count)}


@tool
def find_thymeout_recipes(preferences: Optional[str] = None, recipe_count: int = 10) -> dict:
  """Find recipes on ThymeOut based on provided dietary preference, palate, or other requirements.

  Scrapes live recipes from ThymeOut matching the preferences. When the
  preferences imply a vegetarian or vegan diet, only recipes verified as
  such by the source are returned.

  Args:
    preferences: Dietary preference (eg: "vegetarian") used to filter the results.
    recipe_count: Number of recipes to fetch.

  Returns:
    Dictionary with a list of recipes.
  """
  return {"recipes": scrape_thymeout_recipes(preferences, recipe_count)}


def _create_recipe_finder_agent(
  prompt_client: OrkesPromptClient,
  name: str,
  prompt_name: str,
  prompt_description: str,
  prompt_text: str,
  tools: list,
) -> Agent:
  """Create a recipe finder agent that scrapes a single recipe source.

  Args:
    prompt_client: An instance of OrkesPromptClient to manage prompts.
    name: Agent name (eg: "recipe_finder_bbc_agent").
    prompt_name: Prompt template name on the server.
    prompt_description: Prompt template description.
    prompt_text: Prompt text for this source.
    tools: The agent's tool list.

  Returns:
    An instance of Agent configured for recipe finding.
  """
  prompt = ensure_prompt(
    prompt_client,
    prompt_name,
    prompt_description,
    prompt_text,
    SERVER_MODELS,
  )
  instructions = prompt.template or prompt_text
  return Agent(
    name=name,
    model=SDK_MODEL,
    instructions=instructions,
    tools=tools,
    max_turns=MAX_TURNS,
  )


def create_recipe_finder_bbc_agent(prompt_client: OrkesPromptClient) -> Agent:
  """Creates an agent that finds recipes from BBC Food.

  Args:
    prompt_client: An instance of OrkesPromptClient to manage prompts.

  Returns:
    An instance of Agent configured for BBC recipe finding.
  """
  return _create_recipe_finder_agent(
    prompt_client,
    "recipe_finder_bbc_agent",
    RECIPE_FINDER_BBC_PROMPT_NAME,
    RECIPE_FINDER_BBC_PROMPT_DESCRIPTION,
    RECIPE_FINDER_BBC_PROMPT_TEXT,
    [find_bbc_recipes],
  )


def create_recipe_finder_thymeout_agent(prompt_client: OrkesPromptClient) -> Agent:
  """Creates an agent that finds recipes from ThymeOut.

  Args:
    prompt_client: An instance of OrkesPromptClient to manage prompts.

  Returns:
    An instance of Agent configured for ThymeOut recipe finding.
  """
  return _create_recipe_finder_agent(
    prompt_client,
    "recipe_finder_thymeout_agent",
    RECIPE_FINDER_THYMEOUT_PROMPT_NAME,
    RECIPE_FINDER_THYMEOUT_PROMPT_DESCRIPTION,
    RECIPE_FINDER_THYMEOUT_PROMPT_TEXT,
    [find_thymeout_recipes],
  )
