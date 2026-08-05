from conductor.ai.agents import Agent, tool
from conductor.ai.agents.tool import ToolContext
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient

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
def find_recipes() -> dict:
  """Find recipes based on provided dietary preference, palate, or other requirements.

  Returns:
    Dictionary with a list of recipes.
  """
  # Here, we return a static list for demonstration purposes.
  # In a real implementation, this would query a recipe database or API.
  return {
    "recipes": [
      {
        "name": "Pancakes",
        "ingredients": ["2 cups of flour", "3 cups of milk", "2 eggs"],
        "description": "Fluffy pancakes with syrup are the best start to any day.",
        "servings": 4,
      },
      {
        "name": "Omelette",
        "ingredients": ["2 eggs", "1/2 cup of shredded cheese", "1 cup of spinach", "1/2 cup of mushrooms"],
        "description": "A classic omelette with your choice of fillings.",
        "servings": 1,
      },
      {
        "name": "Grilled Cheese Sandwich",
        "ingredients": ["2 slices of bread", "1 slice of cheese", "1 tablespoon of butter"],
        "description": "A simple yet satisfying grilled cheese sandwich.",
        "servings": 1,
      },
      {
        "name": "Steak and Eggs",
        "ingredients": ["200g of steak", "2 eggs", "1 pinch of salt", "1 pinch of pepper"],
        "description": "A hearty meal of grilled steak and perfectly cooked eggs.",
        "servings": 1,
      },
      {
        "name": "Chicken Salad",
        "ingredients": ["200g of cooked chicken", "1 head of lettuce", "2 tomatoes", "3 tablespoons of dressing"],
        "description": "A refreshing chicken salad with a variety of fresh vegetables.",
        "servings": 2,
      },
      {
        "name": "Spaghetti Bolognese",
        "ingredients": ["200g of spaghetti", "400g of ground beef", "1 cup of tomato sauce", "1 onion", "2 cloves of garlic"],
        "description": "A classic Italian pasta dish with a rich, meaty sauce.",
        "servings": 4,
      },
      {
        "name": "Caesar Salad",
        "ingredients": ["1 head of romaine lettuce", "1 cup of croutons", "1/2 cup of parmesan cheese", "3 tablespoons of Caesar dressing"],
        "description": "Crisp romaine lettuce with crunchy croutons and creamy dressing.",
        "servings": 2,
      },
      {
        "name": "Tacos",
        "ingredients": ["6 taco shells", "300g of ground beef", "1 cup of shredded lettuce", "1 cup of shredded cheese", "1/2 cup of salsa"],
        "description": "Ground beef tacos topped with lettuce, cheese, and salsa.",
        "servings": 3,
      },
      {
        "name": "Stir-Fried Vegetables",
        "ingredients": ["1 cup of broccoli", "2 carrots", "2 bell peppers", "2 tablespoons of soy sauce"],
        "description": "A colorful mix of vegetables stir-fried in soy sauce.",
        "servings": 2,
      },
      {
        "name": "Fruit Smoothie",
        "ingredients": ["1 banana", "1 cup of strawberries", "1/2 cup of yogurt", "1 tablespoon of honey"],
        "description": "A creamy blend of banana, strawberries, and yogurt.",
        "servings": 2,
      },
      {
        "name": "Kraft Dinner",
        "ingredients": ["1 box of Kraft Mac & Cheese", "2 cups of water", "1/4 cup of milk", "2 tablespoons of butter"],
        "description": "If I had a million dollars we'd never have to eat it again. But we would, with all the *fanciest* ketchups.",
        "servings": 2,
      },
      {
        "name": "spam spam spam spam spam spam baked beans spam spam spam",
        "ingredients": ["1 can of spam", "1 can of baked beans"],
        "description": "Beans are off...can I have spam instead??",
        "servings": 4,
      },
      {
        "name": "Lobster Thermidor a Crevette with a mornay sauce served in a Provencale manner with shallots and aubergines garnished with truffle pate, brandy and with a fried egg on top and spam",
        "ingredients": ["1 lobster", "200g of shrimp", "1/2 cup of mornay sauce", "2 shallots", "1 aubergine", "50g of truffle pate", "1 shot of brandy", "1 egg", "1 slice of spam"],
        "description": "A Bromley specialty.",
        "servings": 2,
      },
    ]
  }
  
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