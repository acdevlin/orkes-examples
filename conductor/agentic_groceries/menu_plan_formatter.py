"""
Worker that formats the menu planner agent's text output into a readable line
array for the workflow output, dropping the redundant ingredient list.
"""

import re

from conductor.client.automator.task_handler import get_registered_worker_names
from conductor.client.http.models.task_def import TaskDef
from conductor.client.worker.worker_task import worker_task

_TASK_DEF = TaskDef(
  name="format_menu_plan",
  retry_count=0,
  timeout_seconds=60,
  response_timeout_seconds=30,
)


@worker_task(
  task_definition_name="format_menu_plan",
  task_def=_TASK_DEF,
  register_task_def=True,
  overwrite_task_def=True,
)
def format_menu_plan(text: str) -> dict:
  """Format the menu planner agent's text into a readable line array.

  Normalizes whitespace, drops everything from the "Required Ingredients"
  section onward (redundant with the workflow's shopping_list output), and
  returns the remaining lines as a list so the workflow output renders as a
  readable multi-line array instead of a single escaped string.

  Args:
    text: The menu planner agent's final response text.

  Returns:
    Dictionary with the formatted plan under the "result" key.

  Raises:
    ValueError: If no menu plan text was received.
  """
  if not text:
    raise ValueError("No menu plan text received from the menu planner agent.")
  text = text.replace("\r\n", "\n")
  text = re.sub(r"\n{3,}", "\n\n", text).strip()
  lines = []
  for line in text.split("\n"):
    if "Required Ingredients" in line:
      break
    lines.append(line)
  while lines and not lines[-1].strip():
    lines.pop()
  return {"result": lines}


def ensure_format_menu_plan_worker() -> None:
  """Verify the format_menu_plan worker is registered for polling.

  The @worker_task decorator registers the worker in Conductor's global
  decorated-function registry when this module is imported. This helper makes
  that dependency explicit and re-registers the worker if the registration is
  missing, so a deployment self-heals instead of leaving the workflow's
  format_menu_plan task queued forever.

  Args:
    None.

  Returns:
    None.
  """
  if "format_menu_plan" not in get_registered_worker_names():
    worker_task(
      task_definition_name="format_menu_plan",
      task_def=_TASK_DEF,
      register_task_def=True,
      overwrite_task_def=True,
    )(format_menu_plan)
