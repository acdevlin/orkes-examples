"""
Worker that deterministically extracts the recipe JSON from the recipe finder
agent's output text, so the menu planner receives clean structured data instead
of relying on the LLM to re-emit it through prose.
"""

import json
import re

from conductor.client.http.models.task_def import TaskDef
from conductor.client.worker.worker_task import worker_task
from conductor.client.automator.task_handler import get_registered_worker_names

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
def extract_recipes(join_output: dict) -> dict:
  """Extract the recipe JSON arrays from the recipe finder agents' output.

  Each recipe finder agent is prompted to end its response with a markdown
  fenced code block tagged with "json" containing its recipe array. With the
  fork/join workflow, the join task aggregates both agents' outputs keyed by
  their task reference names; every fenced block across the present agents
  is parsed and the recipe dicts from all of them are merged into one list.
  A source whose fork failed is absent from the join output and is skipped.

  Args:
    join_output: The join task's output: a dict keyed by the recipe finder
      task reference names, whose values are the agents' output dicts (each
      with a "text" field embedding recipe data as JSON arrays).

  Returns:
    Dictionary with the merged "recipes" list.

  Raises:
    ValueError: If no fenced block parses to a list of recipe dicts.
  """
  refs = ("recipe_finder_bbc_agent", "recipe_finder_thymeout_agent_ref")
  parts = []
  for ref in refs:
    output = (join_output or {}).get(ref) or {}
    if not isinstance(output, dict):
      continue
    text = output.get("text") or ""
    if text:
      parts.append(text)
  recipes = []
  for match in _FENCE.finditer("\n\n".join(parts)):
    try:
      parsed = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
      continue
    if isinstance(parsed, list):
      recipes += [r for r in parsed if isinstance(r, dict)]
  if recipes:
    return {"recipes": recipes}
  raise ValueError("Could not find a valid recipe JSON array in the recipe finder output.")


def ensure_extract_recipes_worker() -> None:
  """Verify the extract_recipes worker is registered for polling.

  The @worker_task decorator registers the worker in Conductor's global
  decorated-function registry when this module is imported. This helper makes
  that dependency explicit: it checks the registry and re-registers the worker
  if the registration is missing, so a deployment self-heals instead of leaving
  the workflow's extract_recipes task queued forever.

  Args:
    None.

  Returns:
    None.
  """
  if "extract_recipes" not in get_registered_worker_names():
    worker_task(
      task_definition_name="extract_recipes",
      task_def=_TASK_DEF,
      register_task_def=True,
      overwrite_task_def=True,
    )(extract_recipes)
