# Meal And Grocery Planner

This project creates a menu of dinners for the upcoming 7 days and an associated grocery list of ingredients to purchase in order to cook these meals. Running `main.py` deploys the agents and workflow to Orkes Conductor, then runs the workflow locally once by default.

Agent prompts live in `prompts.py` and are synced to Orkes Conductor as prompt templates (the local text is the source of truth) by `ensure_prompt` in `shared_utils.py`. The prompts embedded in the workflow JSON files are also kept in sync: they are patched automatically from `prompts.py` on every deploy, and can be rewritten into the files on demand with `sync_prompts.py`.

Commands:

- `python main.py` — deploy agents, prompts, and the workflow, then run the workflow once locally.
- `python main.py --server` — deploy, then serve local worker tasks polling Orkes Conductor. Keep this terminal running while running the workflow in the Orkes UI.
- `python main.py --deploy-only` — deploy all artifacts, then exit without running the workflow.
- `python sync_prompts.py` — rewrite the agent prompts embedded in the workflow JSON files from `prompts.py`.

## Workflow

The "Meal And Grocery Planner" workflow (`meal_and_grocery_planner_workflow_v1.json`) runs five steps in order:

1. **Recipe Finder** (AGENT) — finds recipes matching the `query` workflow input via the `find_recipes` tool.
2. **Extract Recipes** (worker) — deterministically extracts the recipe JSON from the agent's output (`recipe_extractor.py`).
3. **Menu Planner** (AGENT) — builds a 7-day dinner menu for the `people_count` people via the `create_menu_plan` tool.
4. **Format Menu Plan** (worker) — normalizes whitespace in the menu plan text, drops the redundant ingredient list, and returns the plan as an array of lines for readable workflow output (`menu_plan_formatter.py`).
5. **Shopping List** (AGENT) — adds all required ingredients to a shared shopping list and shows the final list.

The workflow takes two inputs: `query` (the recipe request, eg: "vegetarian dinners") and `people_count` (how many people to plan dinners for).

## Agent 1: Recipe Finder

Finds recipes that meet specified criteria (eg: dietary restrictions) using the `find_recipes` tool and returns them as structured data.

## Agent 2: Menu Planner

Creates a 7-day menu plan from the provided recipes using the `create_menu_plan` tool, scaling ingredient quantities for the requested number of people.

## Agent 3: Shopping List

Assembles a complete shopping list from the menu provided by the previous agent, using the `add_item`, `get_list`, and `clear_list` tools.
