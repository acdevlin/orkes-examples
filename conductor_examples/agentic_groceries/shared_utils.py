"""
Shared utilities across all agents.
"""

from conductor.client.http.models.prompt_template import PromptTemplate
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient

from prompts import (
  MENU_PLANNER_PROMPT_TEXT,
  RECIPE_FINDER_PROMPT_TEXT,
  SHOPPING_LIST_PROMPT_TEXT,
)

_AGENT_PROMPTS = {
  "recipe_finder_agent": RECIPE_FINDER_PROMPT_TEXT,
  "menu_planner_agent": MENU_PLANNER_PROMPT_TEXT,
  "shopping_list_agent": SHOPPING_LIST_PROMPT_TEXT,
}


def patch_workflow_prompts(workflow: dict) -> dict:
  """Overwrite each agent task's embedded instructions in a workflow def
  with the current prompt text from prompts.py.

  Args:
    workflow: A Conductor workflow definition dict loaded from JSON.

  Returns:
    The same workflow dict with the agent instructions patched in place.
  """
  for task in workflow.get("tasks", []):
    agent_config = task.get("metadata", {}).get("agent", {}).get("conductor", {}).get("agentConfig")
    if agent_config is None:
      continue
    prompt = _AGENT_PROMPTS.get(task.get("name"))
    if prompt is not None:
      agent_config["instructions"] = prompt
  return workflow


def ensure_prompt(
  prompt_client: OrkesPromptClient,
  prompt_name: str,
  description: str,
  prompt_template: str,
  models: list[str],
) -> PromptTemplate:
  """Sync a prompt template to the server. Always overwrites the server
  template with the local text, so the source module is authoritative.

  Args:
    prompt_client: Client for saving/reading prompt templates.
    prompt_name: Name of the prompt template on the server.
    description: Description of the prompt template.
    prompt_template: Local prompt text to sync to the server.
    models: Models allowed to use the prompt on the server.

  Returns:
    The prompt template synced to the server.

  Raises:
    RuntimeError: If the prompt template cannot be saved or read back.
  """
  try:
    prompt_client.save_prompt(
      prompt_name=prompt_name,
      description=description,
      prompt_template=prompt_template,
      models=models)
  except Exception as err:
    raise RuntimeError(
      f"Prompt template '{prompt_name}' could not be saved. "
      "Confirm SERVER_URL and your CONDUCTOR_AUTH_KEY/CONDUCTOR_AUTH_SECRET are correct. "
      f"Full error: {err}"
    ) from err
  prompt = prompt_client.get_prompt(prompt_name)
  if prompt is None:
    raise RuntimeError(
      f"Prompt template '{prompt_name}' was saved but could not be read back. "
      "This likely indicates a server-side permissions or propagation issue."
    )
  return prompt
