"""
Creates an Orkes Conductor agent that manages a shared shopping list.
Uses tools that share state across calls via ToolContext.

Requirements:
    - CONDUCTOR_AUTH_KEY and CONDUCTOR_AUTH_SECRET as environment variables
"""

import math
from typing import Optional

from conductor.ai.agents import Agent, tool
from conductor.ai.agents.tool import ToolContext
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient

from prompts.shopping_list import (
  SHOPPING_LIST_PROMPT_TEXT,
  SHOPPING_LIST_PROMPT_NAME,
  SHOPPING_LIST_PROMPT_DESCRIPTION
)
from config.settings import (
  SDK_MODEL,
  MAX_TURNS,
  SERVER_MODELS
)
from utils.shared_utils import ensure_prompt


# US imperial conversions for the metric units recipes use. Only
# same-dimension conversions are performed (weight -> weight, volume ->
# volume); grams cannot be turned into cups without per-ingredient densities.
_GRAM_PER_OZ = 28.349523125
_OZ_PER_LB = 16
_ML_PER_CUP = 236.5882365
_ML_PER_TBSP = 14.7867648
_ML_PER_TSP = 4.92892159375
_KG_PER_LB = 0.45359237
_ML_PER_L = 1000

# Readability thresholds: below these magnitudes a smaller unit is clearer.
_MIN_CUPS = 0.25
_MIN_TBSP = 1

# Attached units (eg: "800g of steak") are never pluralized or spaced.
_ABBREV = ("g", "kg", "ml", "l", "oz", "lb")
# Irregular plurals plus invariant words that keep their form for any quantity.
_IRREGULAR = {
  "tomato": "tomatoes", "potato": "potatoes", "chilli": "chillies",
  "strawberry": "strawberries", "leaf": "leaves", "loaf": "loaves",
  "half": "halves", "knife": "knives",
  "fish": "fish", "sheep": "sheep", "children": "children",
  "people": "people", "men": "men", "women": "women", "deer": "deer",
  "anise": "anise",
}


def to_imperial(amount: float, unit: Optional[str]) -> tuple:
  """Convert a metric amount to a US imperial unit of the same dimension.

  Weight converts to ounces (or pounds above 16oz) and volume converts to
  cups, tablespoons, or teaspoons depending on magnitude. Counts and units
  that are already imperial (or not measurable, eg: "bag", "cm") are left
  unchanged.

  The returned amount is unrounded; rounding is applied by
  ``render_ingredient`` per the unit type (ounces → ceil integer, cups →
  round up to nearest third/fourth, all other units → round up to nearest
  fourth).

  Args:
    amount: Quantity in the current unit.
    unit: The parsed unit (eg: "g" or "ml"), or None for countable items.

  Returns:
    A (amount, unit) pair converted to imperial, or the input unchanged when
    no conversion applies.
  """
  if unit is None:
    return amount, unit
  key = unit.lower()
  if key == "kg":
    return amount / _KG_PER_LB, "lb"
  if key == "g":
    oz = amount / _GRAM_PER_OZ
    if oz >= _OZ_PER_LB:
      return oz / _OZ_PER_LB, "lb"
    return oz, "oz"
  if key == "ml":
    cups = amount / _ML_PER_CUP
    if cups >= _MIN_CUPS:
      return cups, "cup"
    tbsp = amount / _ML_PER_TBSP
    if tbsp >= _MIN_TBSP:
      return tbsp, "tbsp"
    return amount / _ML_PER_TSP, "tsp"
  if key in ("l", "litre", "litres"):
    return amount * _ML_PER_L / _ML_PER_CUP, "cup"
  return amount, unit


def _format_cup_fraction(frac: float) -> str:
  """Convert a fractional cup amount to a string, rounding up to the nearest
  third or fourth.

  The displayed fractions are: 1/4, 1/3, 1/2, 2/3, 3/4 (and 1 for whole cups).
  A small epsilon handles floating-point imprecision.
  """
  if frac <= 0:
    return "0"
  cup_fracs = [
    (1 / 4, "1/4"),
    (1 / 3, "1/3"),
    (1 / 2, "1/2"),
    (2 / 3, "2/3"),
    (3 / 4, "3/4"),
  ]
  for f_val, f_str in cup_fracs:
    if f_val >= frac - 1e-12:
      return f_str
  # frac > 3/4, round up to 1
  return "1"


def _format_other_fraction(frac: float) -> str:
  """Convert a fractional amount (for non-ounce, non-cup units) to a string,
  rounding up to the nearest fourth.

  The displayed fractions are: 1/4, 1/2, 3/4 (and 1 for whole units).
  """
  if frac <= 0:
    return "0"
  other_fracs = [
    (1 / 4, "1/4"),
    (1 / 2, "1/2"),
    (3 / 4, "3/4"),
  ]
  for f_val, f_str in other_fracs:
    if f_val >= frac - 1e-12:
      return f_str
  # frac > 3/4, round up to 1
  return "1"


def _plural_word(word: str) -> str:
  """Pluralize a single countable noun.

  Args:
    word: Word to pluralize (eg: "cup" or "tomato").

  Returns:
    The plural form (eg: "cups" or "tomatoes").
  """
  if word in _IRREGULAR:
    return _IRREGULAR[word]
  if word.endswith("s"):
    # Either already plural (BBC writes countable items in the plural) or a
    # singular word that ends in "s" (eg: "cress"); never double-pluralize.
    return word
  if word.endswith(("x", "ch", "sh")):
    return word + "es"
  if len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
    return word[:-1] + "ies"
  return word + "s"


def plural(word: str) -> str:
  """Pluralize a countable noun, or the final word of a noun phrase.

  Args:
    word: Word or phrase to pluralize (eg: "cup", "tomato", or
      "cherry tomato").

  Returns:
    The plural form (eg: "cups", "tomatoes", or "cherry tomatoes").
  """
  head, sep, last = word.rpartition(" ")
  return f"{head}{sep}{_plural_word(last)}"


def render_ingredient(amount: float, unit: Optional[str], item: str) -> str:
  """Render a scaled ingredient as a single line.

  Args:
    amount: Quantity (unrounded; rounding is applied per unit type below).
    unit: Unit of measure, or None for countable items (eg: "egg").
    item: Ingredient name (eg: "flour" or "shredded cheese").

  Returns:
    A single ingredient line (eg: "15 oz of chickpeas", "1/3 cup of flour",
    "3 eggs").
  """
  if unit is None or unit == "null" or unit == "of":
    # Countable item (e.g. eggs, tomatoes).
    # For shopping: fractional amounts < 1 round up to 1 (smallest purchasable unit).
    # Amounts >= 1 round to nearest integer, with fraction display for 1/2, 1/4, 3/4.
    if amount <= 1:
      return f"1 {item}"
    rounded = round(amount)
    if abs(amount - rounded) < 0.01 and amount != rounded:
        # Display as fraction for common fractions
        if abs(amount - 0.5) < 0.01:
            frac = "1/2"
        elif abs(amount - 0.25) < 0.01:
            frac = "1/4"
        elif abs(amount - 0.75) < 0.01:
            frac = "3/4"
        else:
            frac = str(int(round(amount)))
        return f"{frac} {item}"
    return f"{int(rounded)} {item}"

  if unit == "oz":
    # Round up to nearest integer.
    qty = int(math.ceil(amount))
    return f"{qty} oz of {item}"

  if unit == "cup":
    # Display as a fraction, rounding up to the nearest third or fourth.
    int_part = int(amount)
    frac = amount - int_part

    if frac <= 1e-12:
      # Effectively a whole number of cups.
      return f"{int_part} cup{'s' if int_part != 1 else ''} of {item}"

    frac_str = _format_cup_fraction(frac)

    if int_part == 0:
      return f"{frac_str} cup of {item}"
    # Mixed number: whole cups plus a fractional cup.
    return f"{int_part} {frac_str} cup of {item}"

  # For all other converted units (lb, tbsp, tsp): fraction, round up to
  # the nearest fourth.
  int_part = int(amount)
  frac = amount - int_part

  if frac <= 1e-12:
    u = unit if unit != "lb" else "lb"
    return f"{int_part} {u} of {item}"

  frac_str = _format_other_fraction(frac)

  if int_part == 0:
    return f"{frac_str} {unit} of {item}"
  return f"{int_part} {frac_str} {unit} of {item}"


@tool
def add_item(
  amount: float,
  unit: Optional[str],
  item: str,
  context: Optional[ToolContext] = None,
) -> dict:
  """Add an ingredient to the shared shopping list.

  Metric amounts are converted to US imperial units automatically (grams and
  kilograms to ounces/pounds; millilitres to cups, tablespoons, or teaspoons),
  so callers pass the amount and unit exactly as given by the recipe source.
  Countable items use a null unit (eg: amount 3, unit null, item "egg").

  Args:
    amount: Numeric quantity of the ingredient.
    unit: Unit of measure (eg: "g", "ml", "kg"), or null for countable items.
    item: Ingredient name (eg: "chickpeas").
    context: Injected tool context with shared state.

  Returns:
    Dictionary confirming the addition.
  """
  converted_amount, converted_unit = to_imperial(amount, unit)
  rendered = render_ingredient(converted_amount, converted_unit, item)
  items = context.state.get("shopping_list", [])
  items.append(rendered)
  context.state["shopping_list"] = items
  return {"added": rendered, "total_items": len(items)}


@tool
def get_list(context: Optional[ToolContext] = None) -> dict:
  """Get the current shopping list from shared state.

  Args:
    context: Injected tool context with shared state.

  Returns:
    Dictionary with the current list.
  """
  items = context.state.get("shopping_list", [])
  return {"items": items, "total_items": len(items)}


@tool
def clear_list(context: Optional[ToolContext] = None) -> dict:
  """Clear the shopping list.

  Args:
    context: Injected tool context with shared state.

  Returns:
    Dictionary confirming the clear.
  """
  context.state["shopping_list"] = []
  return {"status": "cleared"}


def create_shopping_list_agent(prompt_client: OrkesPromptClient) -> Agent:
  """Build the shopping list agent using the server-side prompt template.

  Args:
    prompt_client: Client for saving/reading prompt templates.

  Returns:
    Agent configured with the shopping list tools and instructions.
  """
  prompt = ensure_prompt(
    prompt_client,
    SHOPPING_LIST_PROMPT_NAME,
    SHOPPING_LIST_PROMPT_DESCRIPTION,
    SHOPPING_LIST_PROMPT_TEXT,
    SERVER_MODELS,
  )
  # Pass the template text as a string since the server won't resolve
  # PromptTemplate references into the model's system prompt.
  instructions = prompt.template or SHOPPING_LIST_PROMPT_TEXT
  return Agent(
    name="shopping_list_agent",
    model=SDK_MODEL,
    instructions=instructions,
    tools=[add_item, get_list, clear_list],
    max_turns=MAX_TURNS,
  )
