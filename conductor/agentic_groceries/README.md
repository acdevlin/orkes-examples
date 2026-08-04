# Meal And Grocery Planner

This project creates a menu of dinners for the upcoming 2 weeks and an associated grocery list of ingredients to purchase in order to cook these meals. Running `main.py` generates a workflow with 3 different specialized agents, as detailed below.

Each agent defaults to running locally with a predetermined prompt contained in the `prompts.py` file.

To run locally: `python main.py`

To serve in the Orkes UI using local worker tasks: `python main.py --serve` (you will need to leave the terminal running this command open while running the workflow in the Orkes UI)

## Agent 1: Recipe Finder

TODO

## Agent 2: Menu Planner

TODO

## Agent 3: Shopping List

Assembles a complete shopping list based on the menu provided by the previous agent, then provides an estimated cost for the items on the shopping list.
