"""
Sync the agent prompts embedded in the workflow JSON files from prompts.

The workflow JSON files embed each AGENT task's instructions in its metadata
(metadata.agent.conductor.agentConfig.instructions). This script rewrites
those blocks to match the prompt constants in the workflow JSON files,
so the JSON files never drift from the prompt source of truth.

Usage:
    python sync_prompts.py

Run it after editing any prompt text. Deploys via main.py also
patch the workflow in-memory (see patch_workflow_prompts in shared_utils.py),
so this script is only needed to refresh the checked-in JSON files.
"""
"""

import glob
import json

from utils.shared_utils import patch_workflow_prompts


def main():
  for path in glob.glob("meal_and_grocery_planner_workflow*.json"):
    with open(path, "r") as file:
      workflow = json.load(file)
    patch_workflow_prompts(workflow)
    with open(path, "w") as file:
      json.dump(workflow, file, indent=2)
      file.write("\n")
    print(f"Synced prompts in {path}")


if __name__ == "__main__":
  main()
