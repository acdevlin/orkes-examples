"""
Creates an Orkes Conductor agent that manages a shared shopping list.
Uses tools that share state across calls via ToolContext.

Requirements:
    - CONDUCTOR_AUTH_KEY and CONDUCTOR_AUTH_SECRET as environment variables
"""

from typing import Optional

from conductor.ai.agents import Agent, tool
from conductor.ai.agents.tool import ToolContext
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient

from prompts import (
  SHOPPING_LIST_PROMPT_TEXT,
  SHOPPING_LIST_PROMPT_NAME,
  SHOPPING_LIST_PROMPT_DESCRIPTION
)
from settings import (
  SDK_MODEL,
  MAX_TURNS,
  SERVER_MODELS
)
from shared_utils import ensure_prompt


@tool
def add_item(item: str, context: Optional[ToolContext] = None) -> dict:
  """Add an item to the shared shopping list.

  Args:
    item: The item to add.
    context: Injected tool context with shared state.

  Returns:
    Dictionary confirming the addition.
  """
  items = context.state.get("shopping_list", [])
  items.append(item)
  context.state["shopping_list"] = items
  return {"added": item, "total_items": len(items)}


@tool
def get_list(context: Optional[ToolContext] = None) -> dict:
  """Get the current shopping list from shared state.

  Args:
    context: Injected tool context with shared state.

  Returns:
    Dictionary with the current list.
  """
  items = context.state.get("shopping_list", [])
  return {"items": items, "total_items": len(items)}


@tool
def clear_list(context: Optional[ToolContext] = None) -> dict:
  """Clear the shopping list.

  Args:
    context: Injected tool context with shared state.

  Returns:
    Dictionary confirming the clear.
  """
  context.state["shopping_list"] = []
  return {"status": "cleared"}


def create_shopping_list_agent(prompt_client: OrkesPromptClient) -> Agent:
  """Build the shopping list agent using the server-side prompt template.

  Args:
    prompt_client: Client for saving/reading prompt templates.

  Returns:
    Agent configured with the shopping list tools and instructions.
  """
  prompt = ensure_prompt(
    prompt_client,
    SHOPPING_LIST_PROMPT_NAME,
    SHOPPING_LIST_PROMPT_DESCRIPTION,
    SHOPPING_LIST_PROMPT_TEXT,
    SERVER_MODELS,
  )
  # Pass the template text as a string since the server won't resolve
  # PromptTemplate references into the model's system prompt.
  instructions = prompt.template or SHOPPING_LIST_PROMPT_TEXT
  return Agent(
    name="shopping_list_agent",
    model=SDK_MODEL,
    instructions=instructions,
    tools=[add_item, get_list, clear_list],
    max_turns=MAX_TURNS,
  )
