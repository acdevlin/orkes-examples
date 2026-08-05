"""
Worker that deterministically extracts the recipe JSON from the recipe finder
agent's output text, so the menu planner receives clean structured data instead
of relying on the LLM to re-emit it through prose.
"""

import json
import re

from conductor.client.http.models.task_def import TaskDef
from conductor.client.worker.worker_task import worker_task

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

_DECODER = json.JSONDecoder()

_TASK_DEF = TaskDef(
  name="extract_recipes",
  retry_count=0,
  timeout_seconds=60,
  response_timeout_seconds=30,
)


def _scan_recipes(text: str):
  """Return the first JSON array of dicts embedded in text, or None.

  Args:
    text: Arbitrary text that may embed a JSON array of recipe dicts.

  Returns:
    The first parsed array whose entries are dicts, or None when no such
    array parses.
  """
  idx = text.find("[")
  while idx >= 0:
    try:
      parsed, _ = _DECODER.raw_decode(text, idx)
    except (json.JSONDecodeError, ValueError):
      idx = text.find("[", idx + 1)
      continue
    if isinstance(parsed, list):
      recipes = [r for r in parsed if isinstance(r, dict)]
      if recipes:
        return recipes
    idx = text.find("[", idx + 1)
  return None


@worker_task(
  task_definition_name="extract_recipes",
  task_def=_TASK_DEF,
  register_task_def=True,
  overwrite_task_def=True,
)
def extract_recipes(text: str) -> dict:
  """Extract the recipe JSON array from the recipe finder agent's text.

  Args:
    text: The recipe finder agent's final response, which embeds the recipe
      data as a JSON array in a markdown code block.

  Returns:
    Dictionary with the extracted "recipes" list.

  Raises:
    ValueError: If no parseable recipe array is found in the text.
  """
  if not text:
    raise ValueError("No recipe data received from the recipe finder agent.")
  for match in _FENCE.finditer(text):
    recipes = _scan_recipes(match.group(1).strip())
    if recipes is not None:
      return {"recipes": recipes}
  recipes = _scan_recipes(text)
  if recipes is not None:
    return {"recipes": recipes}
  raise ValueError("Could not find a recipe JSON array in the recipe finder output.")
