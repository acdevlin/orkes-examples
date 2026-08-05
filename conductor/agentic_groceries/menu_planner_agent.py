from conductor.ai.agents import Agent, tool
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient
from datetime import date, timedelta
from typing import Optional

from prompts import (
  MENU_PLANNER_PROMPT_TEXT,
  MENU_PLANNER_PROMPT_NAME,
  MENU_PLANNER_PROMPT_DESCRIPTION
)
from settings import (
  SDK_MODEL,
  MAX_TURNS,
  SERVER_MODELS
)
from shared_utils import ensure_prompt

DEFAULT_MEALS = ["breakfast", "lunch", "dinner"]


@tool
def create_menu_plan(recipes: list, people: int = 1, meal_types: Optional[list] = None) -> dict:
  """Create a 7-day menu plan starting from today.

  Each person consumes one serving of a recipe per meal, so every planned
  meal is sized to serve `people` servings. All three daily meals are
  planned by default, but only the requested meal types are generated when
  given (eg: ["dinner"] for a dinner-only plan).

  Args:
    recipes: List of recipe dicts, each with name, ingredients, and servings.
    people: Number of people to feed per meal.
    meal_types: Meal types to plan; accepts a single type or a list of any
      of ["breakfast", "lunch", "dinner"].

  Returns:
    Dictionary with the 7-day menu plan, the required ingredients, and
    total servings per recipe.

  Raises:
    ValueError: If recipes is empty, people is less than 1, or a meal type
      is not one of ["breakfast", "lunch", "dinner"].
  """
  if not recipes:
    raise ValueError("At least one recipe is required to create a menu plan.")
  if people < 1:
    raise ValueError("At least one person must be fed per meal.")
  
  meals = meal_types or DEFAULT_MEALS
  if isinstance(meals, str):
    meals = [meals]
    
  menu_plan = []
  required_ingredients = []
  total_servings = {}
  slot = 0
  seen = set()

  for i in range(7):
    current = date.today() + timedelta(days=i)
    for meal in meals:
      recipe = recipes[slot % len(recipes)]
      slot += 1
      menu_plan.append({
        "day": current.isoformat(),
        "weekday": current.strftime("%A"),
        "meal": meal,
        "recipe": recipe["name"],
        "servings_per_person": 1,
        "servings_needed": people,
        "ingredients": recipe["ingredients"],
      })
      total_servings[recipe["name"]] = total_servings.get(recipe["name"], 0) + people
      for ingredient in recipe["ingredients"]:
        if ingredient not in seen:
          seen.add(ingredient)
          required_ingredients.append(ingredient)
  return {
    "menu_plan": menu_plan,
    "required_ingredients": required_ingredients,
    "total_servings": total_servings,
  }

def create_menu_planner_agent(prompt_client: OrkesPromptClient) -> Agent:
  """Creates an agent that plans a weekly menu based on available recipes.

  Args:
      prompt_client: An instance of OrkesPromptClient to manage prompts.
  Returns:
      An instance of Agent configured for menu planning.
  """
  # Ensure the prompt is registered with the Orkes Prompt Client
  prompt = ensure_prompt(
    prompt_client,
    MENU_PLANNER_PROMPT_NAME,
    MENU_PLANNER_PROMPT_DESCRIPTION,
    MENU_PLANNER_PROMPT_TEXT,
    SERVER_MODELS,
  )
  instructions = prompt.template or MENU_PLANNER_PROMPT_TEXT
  # Create and return the agent
  return Agent(
    name="menu_planner_agent",
    model=SDK_MODEL,
    instructions=instructions,
    tools=[create_menu_plan],
    max_turns=MAX_TURNS,
  )