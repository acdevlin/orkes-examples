"""
Shared helpers for the BBC Food and ThymeOut recipe scrapers.

Both sites' scrapers normalize ingredients into the same {amount, unit,
item} schema: metric amounts convert to US imperial units (same-dimension
only), and units and countable items are stored singular so the menu
planner pluralizes consistently. This module also holds the shared HTTP
fetch helper and the request-pacing and diet-filter constants used by both
scrapers.
"""

from typing import Optional

import requests

_HEADERS = {
  "User-Agent": (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
  )
}
_REQUEST_DELAY = 0.3
_TIMEOUT = 20
_DEFAULT_AMOUNT = 1
_DEFAULT_SERVINGS = 1
_DIET_FILTER_BUFFER = 5  # Extra candidates fetched to survive diet filtering.

# Known units, longest-first so multi-word units match before single words.
_UNITS = (
  "teaspoon", "teaspoons", "tablespoon", "tablespoons",
  "tbsp", "tbsps", "tsp", "tsps", "cups", "cup",
  "kg", "g", "ml", "l", "litre", "litres", "oz", "lb", "lbs",
  "can", "cans", "clove", "cloves", "slice", "slices", "pinch", "pinches",
  "head", "heads", "bunch", "bunches", "handful", "handfuls", "sprig", "sprigs",
  "sachet", "sachets", "pack", "packs", "packet", "packets", "tub", "tubs",
  "jar", "jars", "tin", "tins", "bottle", "bottles", "bag", "bags",
  "box", "boxes", "carton", "cartons",
  "dash", "drops", "drop", "whole", "half", "quarter", "cm", "mm",
)

# Plural unit spellings seen in the scraped recipe text, mapped to the
# singular form the scrapers store so downstream rendering pluralizes
# consistently.
_PLURAL_UNITS = {
  "cups": "cup", "cans": "can", "tins": "tin", "packs": "pack",
  "bags": "bag", "jars": "jar", "bottles": "bottle", "slices": "slice",
  "cloves": "clove", "pinches": "pinch", "sprigs": "sprig", "heads": "head",
  "bunches": "bunch", "handfuls": "handful", "litres": "litre",
  "teaspoons": "teaspoon", "tablespoons": "tablespoon",
  "tbsps": "tbsp", "tsps": "tsp",
}

# Plural countable items seen in the scraped recipe text, mapped to the
# singular form the scrapers store so downstream rendering pluralizes
# consistently. Only words in this dict are de-pluralized, so singular words
# that happen to end in "s" (eg: "cress", "asparagus") are never mangled.
_PLURAL_ITEMS = {
  "apples": "apple", "apricots": "apricot", "artichokes": "artichoke",
  "aubergines": "aubergine", "avocados": "avocado", "bananas": "banana",
  "beans": "bean", "beetroots": "beetroot", "berries": "berry",
  "biscuits": "biscuit", "blueberries": "blueberry",
  "breadcrumbs": "breadcrumb", "brownies": "brownie", "buns": "bun",
  "burgers": "burger", "carrots": "carrot", "cherries": "cherry",
  "chickpeas": "chickpea", "chillies": "chilli", "chips": "chip",
  "chops": "chop", "cloves": "clove", "cookies": "cookie",
  "courgettes": "courgette", "crackers": "cracker", "crisps": "crisp",
  "crumpets": "crumpet", "cubes": "cube", "cucumbers": "cucumber",
  "cupcakes": "cupcake",
  "curries": "curry", "doughnuts": "doughnut", "drumsticks": "drumstick",
  "dumplings": "dumpling", "eggs": "egg", "fillets": "fillet",
  "flapjacks": "flapjack", "grapes": "grape", "herbs": "herb",
  "kebabs": "kebab", "leaves": "leaf", "leeks": "leek", "lemons": "lemon",
  "lentils": "lentil", "limes": "lime", "meatballs": "meatball",
  "melons": "melon", "muffins": "muffin", "mushrooms": "mushroom",
  "mussels": "mussel", "noodles": "noodle", "nuts": "nut",
  "olives": "olive", "onions": "onion", "oranges": "orange",
  "pancakes": "pancake", "parsnips": "parsnip", "peaches": "peach",
  "pears": "pear", "peas": "pea", "peppers": "pepper",
  "pies": "pie", "pineapples": "pineapple", "pizzas": "pizza",
  "plums": "plum", "potatoes": "potato", "prawns": "prawn",
  "rashers": "rasher", "raspberries": "raspberry", "rolls": "roll",
  "sardines": "sardine", "sausages": "sausage", "scallops": "scallop",
  "scones": "scone", "seeds": "seed", "shallots": "shallot",
  "shapes": "shape", "sprouts": "sprout", "steaks": "steak",
  "sticks": "stick", "strawberries": "strawberry", "swedes": "swede", "tacos": "taco",
  "thighs": "thigh", "tomatoes": "tomato", "tortillas": "tortilla",
  "turnips": "turnip", "wings": "wing",
}

_VEG_KEYWORDS = ("vegetarian", "veggie", "vegan", "meat-free")


def fetch(url: str, params: Optional[dict] = None) -> str:
  """GET a URL and return its text, decoded as UTF-8.

  Args:
    url: Absolute URL to fetch.
    params: Optional query-string parameters.

  Returns:
    The response body as text.

  Raises:
    RuntimeError: If the request fails or the page cannot be fetched.
  """
  try:
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
  except Exception as err:
    raise RuntimeError(f"Could not fetch {url}: {err}") from err
  resp.encoding = "utf-8"
  return resp.text


def singular(unit: Optional[str]) -> Optional[str]:
  """Return the singular form of a unit, if it was captured in the plural.

  Args:
    unit: A unit parsed from the ingredient text (eg: "tins").

  Returns:
    The singular unit (eg: "tin"), or the unit unchanged when it is already
    singular or not countable.
  """
  if unit is None:
    return None
  return _PLURAL_UNITS.get(unit.lower(), unit)


def singular_item(item: str) -> str:
  """De-pluralize the final word of a countable item into its singular form.

  Only words present in _PLURAL_ITEMS are changed, so singular words that
  happen to end in "s" (eg: "cress", "asparagus") are left untouched.

  Args:
    item: The parsed ingredient name (eg: "Brussels sprouts" or "eggs").

  Returns:
    The item with its final word in singular form (eg: "Brussels sprout"
    or "egg").
  """
  head, sep, last = item.rpartition(" ")
  singular_last = _PLURAL_ITEMS.get(last.lower(), last)
  return f"{head}{sep}{singular_last}"



