# Meal And Grocery Planner

This project creates a menu of dinners for the upcoming 7 days and an associated grocery list of ingredients to purchase in order to cook these meals. Running `main.py` deploys the agents and workflow to Orkes Conductor, then runs the workflow locally once by default.

Agent prompts live in `prompts.py` and are synced to Orkes Conductor as prompt templates (the local text is the source of truth) by `ensure_prompt` in `shared_utils.py`.

Commands:

- `python main.py` — deploy agents, prompts, and the workflow, then run the workflow once locally.
- `python main.py --server` — deploy, then serve local worker tasks polling Orkes Conductor. Keep this terminal running while running the workflow in the Orkes UI.
- `python main.py --deploy-only` — deploy all artifacts, then exit without running the workflow.

## Workflow

The "Meal And Grocery Planner" workflow runs five steps in order:

1. **Recipe Finder** (AGENT) — finds recipes matching the requested dietary preference via the `find_recipes` tool.
2. **Extract Recipes** (worker) — deterministically extracts the recipe JSON from the agent's output (`recipe_extractor.py`).
3. **Menu Planner** (AGENT) — builds a 7-day menu plan via the `create_menu_plan` tool.
4. **Human Approval** (HUMAN) — a "Menu Approval" form reviews the menu before the shopping list is built.
5. **Shopping List** (AGENT) — adds all required ingredients to a shared shopping list and shows the final list.

## Agent 1: Recipe Finder

Finds recipes that meet specified criteria (eg: dietary restrictions) using the `find_recipes` tool and returns them as structured data.

## Agent 2: Menu Planner

Creates a 7-day menu plan from the provided recipes using the `create_menu_plan` tool, scaling ingredient quantities for the requested number of people.

## Agent 3: Shopping List

Assembles a complete shopping list from the menu provided by the previous agent, using the `add_item`, `get_list`, and `clear_list` tools.
