"""
Scrape structured recipes from ThymeOut (https://thymeout.app) and parse
them into the recipe schema consumed by the menu planner agent.

ThymeOut is a Blazor app with no JSON API or searchable URL: recipe IDs are
enumerated from the browse page's recipe-photo image URLs, and each recipe
page embeds a JSON-LD Recipe object (name, description, recipeYield) while
ingredients only appear in the page's ingredient table. The shared parsing
helpers from scraper_utils are reused so both sources normalize to the
same {amount, unit, item} ingredient schema with US imperial amounts.
"""

import html
import json
import random
import re
import time
from typing import Optional

from scraper_utils import (
  _DEFAULT_AMOUNT,
  _DEFAULT_SERVINGS,
  _DIET_FILTER_BUFFER,
  _REQUEST_DELAY,
  _UNITS,
  _VEG_KEYWORDS,
  fetch,
  singular,
  singular_item,
  to_imperial,
)

_BASE = "https://thymeout.app"
_BROWSE_URL = _BASE + "/browse"
_MAX_BROWSE_PAGES = 10  # Safety cap on browse pages scanned for candidates.

# Recipe IDs are the 24-char Mongo-style ObjectId in each badge's photo URL.
_RECIPE_ID_RE = re.compile(r"/api/Images/recipes/([a-f0-9]{24})")
_JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
_TITLE_RE = re.compile(r'<h1 class="recipe-title"[^>]*>(.*?)</h1>', re.S)
# Ingredient rows split quantity ("600") from text ("ml water", "onion, diced").
_INGREDIENT_RE = re.compile(
  r'<td class="quantity"[^>]*>(.*?)</td>\s*'
  r'<td class="ingredient-text"[^>]*>(.*?)</td>',
  re.S,
)
_DIGITS_RE = re.compile(r"\d+")


def recipe_paths(target: int) -> list:
  """Collect recipe URL paths from the thymeout browse pages.

  Args:
    target: Minimum number of paths to collect.

  Returns:
    A list of recipe URL paths (eg: "/recipes/6a710915507f8d89800e14e1"),
    sorted and unique. Fewer than `target` when the catalog is smaller.
  """
  paths = set()
  page = 1
  while len(paths) < target:
    url = _BROWSE_URL if page == 1 else f"{_BROWSE_URL}?page={page}"
    ids = set(re.findall(_RECIPE_ID_RE, fetch(url)))
    if not ids:
      break
    new = {f"/recipes/{rid}" for rid in ids} - paths
    if not new:
      break
    paths |= new
    if page >= _MAX_BROWSE_PAGES:
      break
    page += 1
    time.sleep(_REQUEST_DELAY)
  return sorted(paths)


def get_recipe(path: str) -> tuple:
  """Parse a thymeout recipe page into its JSON-LD node, title, and rows.

  Args:
    path: Recipe URL path (eg: "/recipes/6a710915507f8d89800e14e1").

  Returns:
    A (node, title, rows) tuple: the JSON-LD Recipe dict, the page's <h1>
    title (eg: "Vegetarian Miso Soup", without the author suffix), and the
    ingredient table as (quantity, text) row pairs.

  Raises:
    RuntimeError: If the page has no usable JSON-LD recipe data.
  """
  text = fetch(_BASE + path)
  title = re.search(_TITLE_RE, text)
  title = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else ""
  rows = [
    (q.strip(), re.sub(r"<[^>]+>", "", t).strip())
    for q, t in re.findall(_INGREDIENT_RE, text)
  ]
  match = re.search(_JSON_LD_RE, text)
  if not match:
    raise RuntimeError(f"No JSON-LD found on recipe page {path}.")
  try:
    blob = json.loads(match.group(1))
  except json.JSONDecodeError as err:
    raise RuntimeError(f"Invalid JSON-LD on recipe page {path}: {err}") from err
  if isinstance(blob, dict) and "@graph" in blob:
    node = next((n for n in blob["@graph"] if n.get("@type") == "Recipe"), None)
  else:
    node = blob
  if not node or node.get("@type") != "Recipe":
    raise RuntimeError(f"No Recipe node in JSON-LD on recipe page {path}.")
  return node, title, rows


def parse_ingredient(qty: str, text: str) -> dict:
  """Parse a thymeout ingredient row into an {amount, unit, item} dict.

  ThymeOut splits each ingredient into a numeric quantity cell and a text
  cell ("ml water", "g beef sirloin, cubed", or "onion, diced"). A leading
  unit is split off the text, and any prep clause after the first comma is
  dropped ("onion, diced" -> "onion") so countable items pluralize cleanly
  and like ingredients aggregate, mirroring the BBC parser. Metric amounts
  convert to imperial (see to_imperial) and countable items are stored
  singular, so both sources normalize to the same {amount, unit, item}
  schema.

  Args:
    qty: The quantity cell (a decimal number, or "" when absent).
    text: The text cell.

  Returns:
    An {amount, unit, item} dict. Rows without a quantity default to an
    amount of 1 and no unit.
  """
  body = text.strip().split(",")[0].strip()
  unit = None
  rest = body
  for candidate in _UNITS:
    if re.match(rf"^{re.escape(candidate)}(?=\s|$)", rest, re.I):
      unit = candidate
      rest = rest[len(candidate):].strip()
      break
  if qty:
    try:
      amount = float(qty)
    except ValueError:
      amount = _DEFAULT_AMOUNT
      unit = None
  else:
    amount = _DEFAULT_AMOUNT
    unit = None
  if unit is not None:
    amount, unit = to_imperial(amount, singular(unit))
    item = rest
  else:
    item = singular_item(rest or body)
  return {"amount": amount, "unit": unit, "item": item}


def to_schema(node: dict, title: str, rows: list) -> dict:
  """Convert a thymeout recipe page into the project recipe schema.

  Args:
    node: The JSON-LD Recipe dict.
    title: The page's <h1> title (eg: "Vegetarian Miso Soup").
    rows: The ingredient (quantity, text) rows from the page.

  Returns:
    A recipe dict with name, ingredients, servings, description, and a
    vegetarian flag. ThymeOut exposes no explicit diet field, so vegetarian
    is inferred from the recipe's name, keywords, and description.
  """
  name = html.unescape(title.strip()) if title else re.sub(
    r"\s+by\s+.+$", "", str(node.get("name") or ""), flags=re.I
  ).strip()
  description = re.sub(
    r"\s+", " ", html.unescape(str(node.get("description") or ""))
  ).strip()
  keywords = html.unescape(str(node.get("keywords") or ""))
  haystack = f"{name} {keywords} {description}".lower()
  vegetarian = any(word in haystack for word in _VEG_KEYWORDS)
  match = re.search(_DIGITS_RE, str(node.get("recipeYield") or "1"))
  servings = int(match.group()) if match else _DEFAULT_SERVINGS
  return {
    "name": name,
    "ingredients": [parse_ingredient(q, t) for q, t in rows if t],
    "description": description,
    "servings": servings,
    "vegetarian": vegetarian,
  }


def scrape_recipes(preferences: Optional[str], recipe_count: int) -> list:
  """Scrape up to `recipe_count` recipes from thymeout.app.

  Enumerates recipe IDs from the browse page(s), fetches each recipe page,
  and parses it into the {name, ingredients, servings, description,
  vegetarian} schema. ThymeOut has no search endpoint, so dietary
  preferences are applied as a post-parse filter on the vegetarian flag;
  unqualified requests return a random sample of the catalog.

  Args:
    preferences: Dietary/other requirements (eg: "vegetarian"). Only
      vegetarian/vegan filtering is applied, after parsing.
    recipe_count: Number of recipes to fetch.

  Returns:
    A list of recipe dicts in the {name, ingredients, servings, description,
    vegetarian} schema.

  Raises:
    RuntimeError: If no recipes can be found for the query.
  """
  query = (preferences or "").strip()
  want_veg = bool(query) and any(word in query.lower() for word in _VEG_KEYWORDS)
  target = recipe_count + _DIET_FILTER_BUFFER if want_veg else recipe_count
  paths = recipe_paths(target)
  if not paths:
    raise RuntimeError(
      f"No recipes found for '{query or 'general browsing'}'. "
      "Confirm the ThymeOut site is reachable."
    )
  if not want_veg and target < len(paths):
    # The catalog is small, so when filtering by diet every candidate is
    # scanned to avoid randomly missing the few matching recipes.
    paths = random.sample(paths, target)
  recipes = []
  for path in paths:
    try:
      node, title, rows = get_recipe(path)
    except RuntimeError as err:
      print(f"  SKIP {path}: {err}")
      continue
    recipe = to_schema(node, title, rows)
    if want_veg and not recipe["vegetarian"]:
      continue
    recipes.append(recipe)
    if len(recipes) >= recipe_count:
      break
    time.sleep(_REQUEST_DELAY)
  if not recipes:
    raise RuntimeError(
      f"None of the {len(paths)} candidate recipes were suitable for '{query}'."
    )
  return recipes
