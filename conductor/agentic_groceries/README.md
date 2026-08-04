# Meal And Grocery Planner

This project creates a menu of dinners for the upcoming 2 weeks and an associated grocery list of ingredients to purchase in order to cook these meals. Running `main.py` generates a workflow with 3 different specialized agents, as detailed below.

Each agent defaults to running locally with a predetermined prompt contained in the `main()` method of each python file. To run in the Orkes Conductor UI, instead provide the --serve flag which will use conductor.ai.agents.AgentRuntime.serve() to use local workers to execute the agents' tasks.

## Agent 1: Recipe Finder

TBD

## Agent 2: Menu Planner

TBD

## Agent 3: Shopping List

Assembles a complete shopping list based on the menu provided by the previous agent, then provides an estimated cost for the items on the shopping list.
