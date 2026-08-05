from conductor.ai.agents import Agent, tool
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient
from typing import Optional

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
def find_recipes(preferences: Optional[str] = None) -> dict:
  """Find recipes based on provided dietary preference, palate, or other requirements.

  Args:
    preferences: Dietary preference (eg: "vegetarian") used to filter the results.

  Returns:
    Dictionary with a list of recipes.
  """
  # Here, we return a static list for demonstration purposes.
  # In a real implementation, this would query a recipe database or API.
  recipes = [
    {
      "name": "Pancakes",
      "ingredients": [
        {"amount": 2, "unit": "cup", "item": "flour"},
        {"amount": 3, "unit": "cup", "item": "milk"},
        {"amount": 2, "unit": None, "item": "egg"},
      ],
      "description": "Fluffy pancakes with syrup are the best start to any day.",
      "servings": 4,
      "vegetarian": True,
    },
    {
      "name": "Omelette",
      "ingredients": [
        {"amount": 2, "unit": None, "item": "egg"},
        {"amount": 0.5, "unit": "cup", "item": "shredded cheese"},
        {"amount": 1, "unit": "cup", "item": "spinach"},
        {"amount": 0.5, "unit": "cup", "item": "mushrooms"},
      ],
      "description": "A classic omelette with your choice of fillings.",
      "servings": 1,
      "vegetarian": True,
    },
    {
      "name": "Grilled Cheese Sandwich",
      "ingredients": [
        {"amount": 2, "unit": "slice", "item": "bread"},
        {"amount": 1, "unit": "slice", "item": "cheese"},
        {"amount": 1, "unit": "tablespoon", "item": "butter"},
      ],
      "description": "A simple yet satisfying grilled cheese sandwich.",
      "servings": 1,
      "vegetarian": True,
    },
    {
      "name": "Steak and Eggs",
      "ingredients": [
        {"amount": 200, "unit": "g", "item": "steak"},
        {"amount": 2, "unit": None, "item": "egg"},
        {"amount": 1, "unit": "pinch", "item": "salt"},
        {"amount": 1, "unit": "pinch", "item": "pepper"},
      ],
      "description": "A hearty meal of grilled steak and perfectly cooked eggs.",
      "servings": 1,
      "vegetarian": False,
    },
    {
      "name": "Chicken Salad",
      "ingredients": [
        {"amount": 200, "unit": "g", "item": "cooked chicken"},
        {"amount": 1, "unit": "head", "item": "lettuce"},
        {"amount": 2, "unit": None, "item": "tomato"},
        {"amount": 3, "unit": "tablespoon", "item": "dressing"},
      ],
      "description": "A refreshing chicken salad with a variety of fresh vegetables.",
      "servings": 2,
      "vegetarian": False,
    },
    {
      "name": "Spaghetti Bolognese",
      "ingredients": [
        {"amount": 200, "unit": "g", "item": "spaghetti"},
        {"amount": 400, "unit": "g", "item": "ground beef"},
        {"amount": 1, "unit": "cup", "item": "tomato sauce"},
        {"amount": 1, "unit": None, "item": "onion"},
        {"amount": 2, "unit": "clove", "item": "garlic"},
      ],
      "description": "A classic Italian pasta dish with a rich, meaty sauce.",
      "servings": 4,
      "vegetarian": False,
    },
    {
      "name": "Caesar Salad",
      "ingredients": [
        {"amount": 1, "unit": "head", "item": "romaine lettuce"},
        {"amount": 1, "unit": "cup", "item": "croutons"},
        {"amount": 0.5, "unit": "cup", "item": "parmesan cheese"},
        {"amount": 3, "unit": "tablespoon", "item": "Caesar dressing"},
      ],
      "description": "Crisp romaine lettuce with crunchy croutons and creamy dressing.",
      "servings": 2,
      "vegetarian": True,
    },
    {
      "name": "Tacos",
      "ingredients": [
        {"amount": 6, "unit": None, "item": "taco shell"},
        {"amount": 300, "unit": "g", "item": "ground beef"},
        {"amount": 1, "unit": "cup", "item": "shredded lettuce"},
        {"amount": 1, "unit": "cup", "item": "shredded cheese"},
        {"amount": 0.5, "unit": "cup", "item": "salsa"},
      ],
      "description": "Ground beef tacos topped with lettuce, cheese, and salsa.",
      "servings": 3,
      "vegetarian": False,
    },
    {
      "name": "Stir-Fried Vegetables",
      "ingredients": [
        {"amount": 1, "unit": "cup", "item": "broccoli"},
        {"amount": 2, "unit": None, "item": "carrot"},
        {"amount": 2, "unit": None, "item": "bell pepper"},
        {"amount": 2, "unit": "tablespoon", "item": "soy sauce"},
      ],
      "description": "A colorful mix of vegetables stir-fried in soy sauce.",
      "servings": 2,
      "vegetarian": True,
    },
    {
      "name": "Fruit Smoothie",
      "ingredients": [
        {"amount": 1, "unit": None, "item": "banana"},
        {"amount": 1, "unit": "cup", "item": "strawberries"},
        {"amount": 0.5, "unit": "cup", "item": "yogurt"},
        {"amount": 1, "unit": "tablespoon", "item": "honey"},
      ],
      "description": "A creamy blend of banana, strawberries, and yogurt.",
      "servings": 2,
      "vegetarian": True,
    },
    {
      "name": "Kraft Dinner",
      "ingredients": [
        {"amount": 1, "unit": "box", "item": "Kraft Mac & Cheese"},
        {"amount": 2, "unit": "cup", "item": "water"},
        {"amount": 0.25, "unit": "cup", "item": "milk"},
        {"amount": 2, "unit": "tablespoon", "item": "butter"},
      ],
      "description": "If I had a million dollars we'd never have to eat it again. But we would, with all the *fanciest* ketchups.",
      "servings": 2,
      "vegetarian": True,
    },
    {
      "name": "spam spam spam spam spam spam baked beans spam spam spam",
      "ingredients": [
        {"amount": 1, "unit": "can", "item": "spam"},
        {"amount": 1, "unit": "can", "item": "baked beans"},
      ],
      "description": "Beans are off...can I have spam instead??",
      "servings": 4,
      "vegetarian": False,
    },
    {
      "name": "Lobster Thermidor a Crevette with a mornay sauce served in a Provencale manner with shallots and aubergines garnished with truffle pate, brandy and with a fried egg on top and spam",
      "ingredients": [
        {"amount": 1, "unit": None, "item": "lobster"},
        {"amount": 200, "unit": "g", "item": "shrimp"},
        {"amount": 0.5, "unit": "cup", "item": "mornay sauce"},
        {"amount": 2, "unit": None, "item": "shallot"},
        {"amount": 1, "unit": None, "item": "aubergine"},
        {"amount": 50, "unit": "g", "item": "truffle pate"},
        {"amount": 1, "unit": "shot", "item": "brandy"},
        {"amount": 1, "unit": None, "item": "egg"},
        {"amount": 1, "unit": "slice", "item": "spam"},
      ],
      "description": "A Bromley specialty.",
      "servings": 2,
      "vegetarian": False,
    },
  ]
  if preferences and any(
    word in preferences.lower() for word in ("vegetarian", "veggie", "vegan", "meat-free")
  ):
    recipes = [r for r in recipes if r["vegetarian"]]
  return {"recipes": recipes}
  
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