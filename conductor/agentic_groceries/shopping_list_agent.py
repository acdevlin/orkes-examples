"""
Creates an Orkes Conductor agent that manages a shared shopping list.
Uses tools that share state across calls via ToolContext.

Requirements:
    - CONDUCTOR_AUTH_KEY and CONDUCTOR_AUTH_SECRET as environment variables
    - CONDUCTOR_AGENT_SDK_MODEL=openai/gpt-4o-mini as an environment
"""

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

@tool
def add_item(item: str, context: ToolContext = None) -> dict:
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
def get_list(context: ToolContext = None) -> dict:
    """Get the current shopping list from shared state.

    Args:
        context: Injected tool context with shared state.

    Returns:
        Dictionary with the current list.
    """
    items = context.state.get("shopping_list", [])
    return {"items": items, "total_items": len(items)}


@tool
def clear_list(context: ToolContext = None) -> dict:
    """Clear the shopping list.

    Args:
        context: Injected tool context with shared state.

    Returns:
        Dictionary confirming the clear.
    """
    context.state["shopping_list"] = []
    return {"status": "cleared"}


def ensure_prompt(prompt_client: OrkesPromptClient):
    """Sync the shopping list prompt template to the server. Always overwrites
    the server template with the local text, so prompts.py is authoritative.

    Args:
        prompt_client: Client for saving/reading prompt templates.

    Returns:
        None.

    Raises:
        RuntimeError: If the prompt template cannot be saved or read back.
    """
    try:
        prompt_client.save_prompt(
            prompt_name=SHOPPING_LIST_PROMPT_NAME,
            description=SHOPPING_LIST_PROMPT_DESCRIPTION,
            prompt_template=SHOPPING_LIST_PROMPT_TEXT,
            models=SERVER_MODELS)
    except Exception as err:
        raise RuntimeError(
            f"Prompt template '{SHOPPING_LIST_PROMPT_NAME}' could not be saved. "
            "Confirm CONDUCTOR_SERVER_URL and your auth key/secret are correct."
            f"Full error: {err}"
        ) from err
    if prompt_client.get_prompt(SHOPPING_LIST_PROMPT_NAME) is None:
        raise RuntimeError(
            f"Prompt template '{SHOPPING_LIST_PROMPT_NAME}' was saved but could not be read back. "
            "This likely indicates a server-side permissions or propagation issue."
        )


def create_shopping_list_agent(prompt_client: OrkesPromptClient) -> Agent:
    """Build the shopping list agent using the server-side prompt template.

    Args:
        prompt_client: Client for saving/reading prompt templates.

    Returns:
        Agent configured with the shopping list tools and instructions.
    """
    ensure_prompt(prompt_client)
    # Pass the template text as a string since the server won't resolve
    # PromptTemplate references into the model's system prompt.
    prompt = prompt_client.get_prompt(SHOPPING_LIST_PROMPT_NAME)
    instructions = (prompt.template if prompt is not None else "") or SHOPPING_LIST_PROMPT_TEXT
    return Agent(
        name="shopping_list_agent",
        model=SDK_MODEL,
        instructions=instructions,
        tools=[add_item, get_list, clear_list],
        max_turns=MAX_TURNS,
    )
