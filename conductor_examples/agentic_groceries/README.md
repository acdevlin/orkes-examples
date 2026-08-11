# Meal And Grocery Planner

This project creates a menu of dinners for the upcoming 7 days and an associated grocery list of ingredients to purchase in order to cook these meals. Running `main.py` deploys the agents and workflow to Orkes Conductor, then runs the workflow locally once by default.

Recipe data is scraped live from [BBC Food](https://www.bbc.co.uk/food) by the `find_recipes` tool (using `requests`); the tool no longer ships a static recipe list. When the request implies a vegetarian or vegan diet, only recipes the source marks as such are returned.

Agent prompts live in `prompts.py` and are synced to Orkes Conductor as prompt templates (the local text is the source of truth) by `ensure_prompt` in `shared_utils.py`. The prompts embedded in the workflow JSON files are also kept in sync: they are patched automatically from `prompts.py` on every deploy, and can be rewritten into the files on demand with `sync_prompts.py`.

Commands:

- `python main.py` — deploy agents, prompts, and the workflow, then run the workflow once locally.
- `python main.py --server` — deploy, then serve local worker tasks polling Orkes Conductor. Keep this terminal running while running the workflow in the Orkes UI.
- `python main.py --deploy-only` — deploy all artifacts, then exit without running the workflow.
- `python sync_prompts.py` — rewrite the agent prompts embedded in the workflow JSON files from `prompts.py`.

## Workflow

The "Meal And Grocery Planner" workflow (`meal_and_grocery_planner_workflow_v1.json`) runs six steps in order:

1. **Recipe Finder** (AGENT) — finds recipes matching the `query` workflow input via the `find_recipes` tool.
2. **Extract Recipes** (worker) — deterministically extracts the recipe JSON from the agent's output (`recipe_extractor.py`).
3. **Menu Planner** (AGENT) — builds a 7-day dinner menu for the `people_count` people via the `create_menu_plan` tool.
4. **Human Approval** (HUMAN) — asks a human to approve the proposed menu before any ingredients are purchased.
5. **Format Menu Plan** (worker) — normalizes whitespace in the menu plan text, drops the redundant ingredient list, and returns the plan as an array of lines for readable workflow output (`menu_plan_formatter.py`).
6. **Shopping List** (AGENT) — adds all required ingredients to a shared shopping list and shows the final list.

The workflow takes three inputs: `query` (the recipe request, eg: "vegetarian dinners"), `people_count` (how many people to plan dinners for), and `recipe_count` (how many recipes the finder should fetch).

## Agent 1: Recipe Finder

Finds recipes that meet specified criteria (eg: dietary restrictions) using the `find_recipes` tool and returns them as structured data. The tool scrapes live recipes from BBC Food: it searches for the requested preferences, parses each recipe page's embedded JSON-LD (name, structured ingredients, servings, and diet markers), and drops any result not verified as vegetarian/vegan when the request implies a dietary filter. The `recipe_count` argument (default 10) controls how many recipes are fetched, so the request volume can be tuned at the workflow level.

Ingredient amounts are parsed into a structured `{amount, unit, item}` form at scrape time. Metric weights and volumes are converted to US imperial units of the same dimension (grams to ounces/pounds, millilitres to cups/tablespoons/teaspoons; no density-based weight-to-volume conversion is performed), and the explicit weight always wins over a container count, so "400g tin of chickpeas" becomes 14.1oz of chickpeas rather than a nebulous "1 tin". Units and countable items are normalized to their singular form so downstream rendering pluralizes them consistently ("3 tomatoes", not "3 tomatoeses").

## Agent 2: Menu Planner

Creates a 7-day menu plan from the provided recipes using the `create_menu_plan` tool, scaling ingredient quantities for the requested number of people.

## Agent 3: Shopping List

Assembles a complete shopping list from the menu provided by the previous agent, using the `add_item`, `get_list`, and `clear_list` tools.
