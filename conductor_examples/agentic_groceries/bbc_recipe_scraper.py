"""
Scrape structured recipes from BBC Food (https://www.bbc.co.uk/food) and
parse them into the recipe schema consumed by the menu planner agent.
"""

import html
import json
import math
import random
import re
import string
import time
from typing import Optional

import requests

_BASE = "https://www.bbc.co.uk"
_SEARCH_URL = _BASE + "/food/search"
_AZ_URL = _BASE + "/food/recipes/a-z/{letter}/1"
_HEADERS = {
  "User-Agent": (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
  )
}
_REQUEST_DELAY = 0.3
_TIMEOUT = 20
_RECIPES_PER_PAGE = 24  # BBC Food search results per page.
_DIET_FILTER_BUFFER = 5  # Extra candidates fetched to survive diet filtering.
_DEFAULT_AMOUNT = 1
_DEFAULT_SERVINGS = 1

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

# Container nouns that describe how a weighted ingredient is sold; a leading
# weight ("400g tin of chickpeas") describes the container, not the quantity.
_CONTAINERS = (
  "tin", "can", "jar", "pack", "packet", "bottle", "bag", "tub",
  "carton", "sachet", "box",
)

# Leading descriptors stripped from ingredient lines before parsing.
_DESCRIPTORS = (
  "small", "medium", "large", "big", "fresh", "ripe", "chopped", "grated",
  "finely", "roughly", "crushed", "pitted", "peeled", "seeded", "tinned",
  "frozen", "skinless", "boneless", "low-fat", "full-fat", "reduced-fat",
  "ready-made", "unsalted", "salted", "extra", "virgin", "hot", "cold",
  "warm", "sea", "rock", "semi", "soft", "splash", "drizzle",
  "few", "good", "generous", "free-range",
)

_FRACTIONS = {
  "½": 0.5, "⅓": 1 / 3, "¼": 0.25, "¾": 0.75, "⅔": 2 / 3,
  "⅕": 0.2, "⅖": 0.4, "⅗": 0.6, "⅘": 0.8, "⅙": 1 / 6,
  "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
}

_VEG_KEYWORDS = ("vegetarian", "veggie", "vegan", "meat-free")

# JSON-LD description values that carry no real recipe info; these pages fall
# back to the page meta description or a constructed summary instead.
_GENERIC_DESCRIPTIONS = (
  "bbc food",
  "bbc good food",
  "bbc good food recipe",
  "",
)

# US imperial conversions for the metric units BBC recipes use. Only
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

# Rounding precision per imperial unit.
_OZ_PRECISION = 1
_LB_PRECISION = 2
_CUP_PRECISION = 2
_TBSP_PRECISION = 1
_TSP_PRECISION = 1

# Plural unit spellings seen in BBC text, mapped to the singular form the
# scraper stores so downstream rendering pluralizes consistently.
_PLURAL_UNITS = {
  "cups": "cup", "cans": "can", "tins": "tin", "packs": "pack",
  "bags": "bag", "jars": "jar", "bottles": "bottle", "slices": "slice",
  "cloves": "clove", "pinches": "pinch", "sprigs": "sprig", "heads": "head",
  "bunches": "bunch", "handfuls": "handful", "litres": "litre",
  "teaspoons": "teaspoon", "tablespoons": "tablespoon",
  "tbsps": "tbsp", "tsps": "tsp",
}

# Plural countable items seen in BBC text, mapped to the singular form the
# scraper stores so downstream rendering pluralizes consistently. Only words
# in this dict are de-pluralized, so singular words that happen to end in "s"
# (eg: "cress", "asparagus") are never mangled.
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

# JSON-LD keys on BBC recipe pages.
_LD_GRAPH = "@graph"
_LD_TYPE = "@type"
_LD_RECIPE = "Recipe"
_VEG_DIETS = ("VegetarianDiet", "VeganDiet")

# Alternative quantities like "500g/1lb 2oz", "150g/5.3oz", or
# "500ml/17fl oz", stripped from ingredient lines before anything else. Only
# stripped when a unit precedes the slash so fractions like "1/2 tsp" survive;
# two-word imperial alternatives ("fl oz") and a trailing quantified token
# ("1lb 2oz") are consumed whole.
_ALT_QTY_RE = (
  r"(?<=[a-zA-Z])/\d*(?:\.\d+)?(?:[¼½¾⅓⅔⅛])?\s*[a-zA-Z]+"
  r"(?:\s+(?:\d+[a-zA-Z]+|oz|lb|fl))?\.?(?=\s|$)"
)

# "2 x 400g tins of chickpeas", and the bare form without a per-container
# weight ("2 x cans of tomatoes").
_COUNT_PACK_RE = r"^(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+"
_COUNT_PACK_BARE_RE = r"^(\d+)\s*[x×]\s+"

# A leading weight describing a container ("400g tin of chickpeas").
_WEIGHTED_CONTAINER_RE = (
  r"^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+(" + "|".join(_CONTAINERS) + r")\b(.*)$"
)

_ARTICLES_RE = r"^(a|an|some)\s+"
_QTY_TOKEN_RE = r"^(\d+(?:\.\d+)?(?:/\d+)?|½|¼|¾|⅓|⅔|⅛)\s*"
_PREP_RE = r"^(of|to serve|for|with)\s+"
_RECIPE_URL_RE = r'href="(/food/recipes/[a-z0-9_-]+)"'
_JSON_LD_RE = r'<script data-rh="true" type="application/ld\+json">(.*?)</script>'
_NUTRITION_RE = r"\s*Each serving provides.*$"
_DIGITS_RE = r"\d+"


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


def search_urls(query: Optional[str], pages: int) -> list:
  """Collect recipe URL paths from BBC search (or a-z browse) result pages.

  Args:
    query: Search term; when empty, a random a-z browse page is used so an
      unqualified request still returns recipes.
    pages: Number of result pages to fetch.

  Returns:
    A list of recipe URL paths (eg: "/food/recipes/slug_12345").
  """
  paths = []
  for page in range(1, pages + 1):
    if query:
      url, params = _SEARCH_URL, {"q": query, "page": page}
    else:
      letter = random.choice(string.ascii_lowercase)
      url, params = _AZ_URL.format(letter=letter), None
    paths += re.findall(_RECIPE_URL_RE, fetch(url, params))
    time.sleep(_REQUEST_DELAY)
  return sorted(set(paths))


def _meta_description(text: str) -> str:
  """Extract the page's meta description, if any.

  Args:
    text: A recipe page's HTML.

  Returns:
    The og:description (or name="description") content, HTML-unescaped, or
    an empty string when neither tag is present.
  """
  for pattern in (r'property="og:description"', r'name="description"'):
    match = re.search(r"<meta[^>]*" + pattern + r"[^>]*>", text)
    if match:
      content = re.search(r'content="([^"]*)"', match.group(0))
      if content:
        return html.unescape(content.group(1)).strip()
  return ""


def get_recipe(path: str) -> tuple:
  """Parse the JSON-LD Recipe object from a recipe page.

  Args:
    path: Recipe URL path (eg: "/food/recipes/slug_12345").

  Returns:
    A (node, meta_description) tuple: the Recipe node from the page's
    JSON-LD graph, and the page's meta description (which some recipes carry
    instead of a useful JSON-LD description).

  Raises:
    RuntimeError: If the page has no usable JSON-LD recipe data.
  """
  text = fetch(_BASE + path)
  match = re.search(_JSON_LD_RE, text, re.S)
  if not match:
    raise RuntimeError(f"No JSON-LD found on recipe page {path}.")
  try:
    blob = json.loads(match.group(1))
  except json.JSONDecodeError as err:
    raise RuntimeError(f"Invalid JSON-LD on recipe page {path}: {err}") from err
  for node in blob.get(_LD_GRAPH, []):
    if node.get(_LD_TYPE) == _LD_RECIPE:
      return node, _meta_description(text)
  raise RuntimeError(f"No Recipe node in JSON-LD on recipe page {path}.")


def parse_amount(raw: str) -> Optional[float]:
  """Parse a leading quantity token: a plain or decimal number, a fraction
  ("1/2"), or a unicode fraction ("½").

  Args:
    raw: Text beginning with a quantity.

  Returns:
    The parsed amount, or None if no quantity is present.
  """
  match = re.match(r"^(\d+)\s*/\s*(\d+)", raw)
  if match:
    return float(match.group(1)) / float(match.group(2))
  match = re.match(r"^(\d+(?:\.\d+)?)", raw)
  if match:
    return float(match.group(1))
  for glyph, value in _FRACTIONS.items():
    if raw.startswith(glyph):
      return value
  return None


def to_imperial(amount: float, unit: Optional[str]) -> tuple:
  """Convert a metric amount to a US imperial unit of the same dimension.

  Weight converts to ounces (or pounds above 16oz) and volume converts to
  cups, tablespoons, or teaspoons depending on magnitude. Counts and units
  that are already imperial (or not measurable, eg: "bag", "cm") are left
  unchanged.

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
    return round(amount / _KG_PER_LB, _LB_PRECISION), "lb"
  if key == "g":
    oz = amount / _GRAM_PER_OZ
    if oz >= _OZ_PER_LB:
      return round(oz / _OZ_PER_LB, _LB_PRECISION), "lb"
    return round(oz, _OZ_PRECISION), "oz"
  if key == "ml":
    cups = amount / _ML_PER_CUP
    if cups >= _MIN_CUPS:
      return round(cups, _CUP_PRECISION), "cup"
    tbsp = amount / _ML_PER_TBSP
    if tbsp >= _MIN_TBSP:
      return round(tbsp, _TBSP_PRECISION), "tbsp"
    return round(amount / _ML_PER_TSP, _TSP_PRECISION), "tsp"
  if key in ("l", "litre", "litres"):
    return round(amount * _ML_PER_L / _ML_PER_CUP, _CUP_PRECISION), "cup"
  return amount, unit


def parse_ingredient(line: str) -> dict:
  """Best-effort parse of a free-text ingredient into {amount, unit, item}.

  Args:
    line: A BBC ingredient line (eg: "200g/7oz penne" or "2 x 400g tins of
      chickpeas").

  Returns:
    A dict with amount, unit (or None), and item (eg: {"amount": 200,
    "unit": "g", "item": "penne"}). Metric amounts are converted to US
    imperial units (see to_imperial) and units and countable items are
    stored in singular form so downstream rendering pluralizes consistently.
    A weight that describes a container ("400g tin of chickpeas") is used as
    the explicit ingredient amount with the container word dropped; a
    container count without a weight ("2 cans of tomatoes") is preserved as a
    count. Unparseable lines fall back to an amount of 1 and the cleaned raw
    text as the item.
  """
  body = line.strip().strip(".")
  body = re.split(r",| \(", body)[0].strip()
  body = re.sub(_ARTICLES_RE, "", body, flags=re.I)
  body = re.sub(r"^(" + "|".join(_DESCRIPTORS) + r")\s+", "", body, flags=re.I).strip()

  # Strip alternative quantities like "500g/1lb 2oz" (see _ALT_QTY_RE).
  body = re.sub(_ALT_QTY_RE, "", body).strip()

  # "2 x 400g tins of chickpeas" or, without a weight, "2 x cans of tomatoes".
  weighted = re.match(_COUNT_PACK_RE, body)
  match = weighted or re.match(_COUNT_PACK_BARE_RE, body)
  if match:
    rest = body[match.end():].strip()
    unit = None
    for candidate in _UNITS:
      if re.match(rf"^{re.escape(candidate)}(?=\s|$)", rest, re.I):
        unit = candidate
        rest = rest[len(candidate):].strip()
        break
    rest = rest.removeprefix("of ").strip()
    if weighted:
      # "2 x 400g tins": the per-container weight is explicit, so the total
      # weight is the amount and the container unit is dropped.
      amount, unit = to_imperial(
        float(weighted.group(1)) * float(weighted.group(2)), weighted.group(3),
      )
    else:
      amount, unit = to_imperial(float(match.group(1)), singular(unit))
    return {
      "amount": amount,
      "unit": unit,
      "item": singular_item(rest) if unit is None else rest,
    }

  # A leading weight describing a container ("400g tin of chickpeas"): the
  # weight is the explicit amount, so convert it and drop the container word.
  match = re.match(_WEIGHTED_CONTAINER_RE, body, re.I)
  if match:
    item = re.sub(_PREP_RE, "", match.group(4).strip()).strip()
    amount, unit = to_imperial(float(match.group(1)), singular(match.group(2).lower()))
    return {"amount": amount, "unit": unit, "item": item}

  amt = parse_amount(body)
  if amt is None:
    return {"amount": _DEFAULT_AMOUNT, "unit": None, "item": body}
  amount = amt
  rest = re.sub(_QTY_TOKEN_RE, "", body).strip()
  unit = None
  for candidate in _UNITS:
    if re.match(rf"^{re.escape(candidate)}(?=\s|$)", rest, re.I):
      unit = candidate
      rest = rest[len(candidate):].strip()
      break
  item = re.sub(_PREP_RE, "", rest.strip()).strip()
  amount, unit = to_imperial(amount, singular(unit))
  if unit is None:
    item = singular_item(item)
  return {"amount": amount, "unit": unit, "item": item}


def to_schema(node: dict, meta_desc: str = "") -> dict:
  """Convert a JSON-LD Recipe node into the project recipe schema.

  Args:
    node: A JSON-LD Recipe dict parsed from a BBC recipe page.
    meta_desc: The page's meta description, used when the JSON-LD
      description is generic or missing.

  Returns:
    A recipe dict with name, ingredients, servings, description, and a
    vegetarian flag derived from suitableForDiet.
  """
  diet = node.get("suitableForDiet") or []
  if isinstance(diet, str):
    diet = [diet]
  vegetarian = any(any(flag in d for flag in _VEG_DIETS) for d in diet)

  name = node.get("name") or node.get("headline") or ""
  description = _clean_description(
    str(node.get("description") or ""),
    meta_desc,
    str(node.get("recipeCategory") or ""),
    str(node.get("recipeCuisine") or ""),
  )

  match = re.search(_DIGITS_RE, str(node.get("recipeYield") or "1"))
  servings = int(match.group()) if match else _DEFAULT_SERVINGS

  return {
    "name": name,
    "ingredients": [parse_ingredient(line) for line in node.get("recipeIngredient", [])],
    "description": description,
    "servings": servings,
    "vegetarian": vegetarian,
  }


def _clean_description(ld_desc: str, meta_desc: str, category: str, cuisine: str) -> str:
  """Pick the most useful description for a recipe.

  Prefers the JSON-LD description (the full editorial text); falls back to
  the page meta description when the JSON-LD text is generic (eg: "BBC
  Food"); and finally constructs a short summary from the recipe category
  and cuisine. A trailing per-serving nutrition sentence is dropped.

  Args:
    ld_desc: The JSON-LD description field.
    meta_desc: The page's meta description.
    category: The recipe category (eg: "Main course").
    cuisine: The recipe cuisine (eg: "Mexican").

  Returns:
    A single-line description string.
  """
  desc = (ld_desc or "").strip()
  if desc.lower() in _GENERIC_DESCRIPTIONS:
    desc = (meta_desc or "").strip()
  desc = re.sub(_NUTRITION_RE, "", desc, flags=re.I | re.S).strip()
  if not desc or desc.lower() in _GENERIC_DESCRIPTIONS:
    parts = [part for part in (category, cuisine) if part]
    desc = "BBC Food recipe" + (f' ({", ".join(parts)}).' if parts else ".")
  return re.sub(r"\s+", " ", desc).strip()


def scrape_recipes(preferences: Optional[str], recipe_count: int) -> list:
  """Scrape up to `recipe_count` recipes from BBC Food for the given preferences.

  Args:
    preferences: Dietary/other requirements (eg: "vegetarian"), used as the
      BBC search term. When empty, random recipes are returned.
    recipe_count: Number of recipes to fetch.

  Returns:
    A list of recipe dicts in the {name, ingredients, servings, description,
    vegetarian} schema.

  Raises:
    RuntimeError: If no recipes can be found for the query.
  """
  query = (preferences or "").strip()
  pages = math.ceil(recipe_count / _RECIPES_PER_PAGE)
  paths = search_urls(query or None, pages)
  if not paths:
    raise RuntimeError(
      f"No recipes found for '{query or 'general browsing'}'. "
      "Confirm the BBC Food site is reachable and the query is valid."
    )

  want_veg = bool(query) and any(word in query.lower() for word in _VEG_KEYWORDS)
  # Fetch a few extra candidates when filtering by diet so `recipe_count` is
  # usually still reached after non-vegetarian results are dropped.
  target = recipe_count + _DIET_FILTER_BUFFER if want_veg else recipe_count
  if target < len(paths):
    paths = random.sample(paths, target)

  recipes = []
  for path in paths:
    try:
      node, meta_desc = get_recipe(path)
    except RuntimeError as err:
      print(f"  SKIP {path}: {err}")
      continue
    recipe = to_schema(node, meta_desc)
    if want_veg and not recipe["vegetarian"]:
      continue
    recipes.append(recipe)
    if len(recipes) >= recipe_count:
      break
    time.sleep(_REQUEST_DELAY)

  if not recipes:
    raise RuntimeError(
      f"None of the {len(paths)} candidate recipes were suitable for "
      f"'{query}'."
    )
  return recipes
