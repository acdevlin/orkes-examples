"""
Worker that deterministically extracts the recipe JSON from the recipe finder
agent's output text, so the menu planner receives clean structured data instead
of relying on the LLM to re-emit it through prose.
"""

import json
import re

from conductor.client.http.models.task_def import TaskDef
from conductor.client.worker.worker_task import worker_task

# Matches a markdown fenced code block, optionally tagged with "json".
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

_TASK_DEF = TaskDef(
  name="extract_recipes",
  retry_count=0,
  timeout_seconds=60,
  response_timeout_seconds=30,
)


@worker_task(
  task_definition_name="extract_recipes",
  task_def=_TASK_DEF,
  register_task_def=True,
  overwrite_task_def=True,
)
def extract_recipes(text: str) -> dict:
  """Extract the recipe JSON array from the recipe finder agent's text.

  The recipe finder agent is prompted to end its response with a markdown
  fenced code block tagged with "json" containing the recipe array, so this
  worker parses and validates that block rather than scanning arbitrary prose.

  Args:
    text: The recipe finder agent's final response, which embeds the recipe
      data as a JSON array in a markdown code block.

  Returns:
    Dictionary with the extracted "recipes" list.

  Raises:
    ValueError: If no fenced block parses to a non-empty list of recipe dicts.
  """
  if not text:
    raise ValueError("No recipe data received from the recipe finder agent.")
  for match in _FENCE.finditer(text):
    try:
      recipes = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
      continue
    if (
      isinstance(recipes, list)
      and recipes
      and all(isinstance(r, dict) for r in recipes)
    ):
      return {"recipes": recipes}
  raise ValueError("Could not find a valid recipe JSON array in the recipe finder output.")
