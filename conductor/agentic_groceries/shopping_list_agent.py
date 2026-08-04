"""
Originally forked from https://github.com/conductor-oss/python-sdk/blob/main/examples/agents/51_shared_state.py

Shared State — tools sharing state across calls via ToolContext.

Tools can read and write to ``context.state``, a dictionary that persists
across all tool calls within the same agent execution. This enables
tools to accumulate data, maintain counters, or pass information between
different tool invocations without relying on the LLM to relay state.

Requirements:
    - CONDUCTOR_SERVER_URL=https://developer.orkescloud.com/api as an environment variable
    - CONDUCTOR_AUTH_KEY and CONDUCTOR_AUTH_SECRET as environment variables
    - CONDUCTOR_AGENT_LLM_MODEL=openai/gpt-4o-mini as an environment
"""

from conductor.ai.agents import Agent, AgentRuntime, tool
from conductor.ai.agents.runtime.config import AgentConfig
from conductor.ai.agents.tool import ToolContext
from conductor.client.configuration.configuration import Configuration
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient

import os

# Required import to avoid pickling error from @tool in the current SDK.
# Should be resolved with this pull: https://github.com/conductor-oss/python-sdk/pull/414
import multiprocessing
multiprocessing.set_start_method("fork", force=True)

# integration name for OpenAI, already saved in your Orkes account
integration_name = "OpenAI_Key"
# model name from LLM provider, already saved in your Orkes account     
model_name = "gpt-4o-mini"
# SDK agent format: integration/model
llm_model = f"{integration_name}/{model_name}"
# server prompt format: integration:model    
models = [f"{integration_name}:{model_name}"]     
server_url = "https://developer.orkescloud.com/api"

SHOPPING_PROMPT = """
    You help manage a shopping list. Use add_item to add items, 
    get_list to view the list, and clear_list to reset it. 
    
    IMPORTANT: Always add all items first, then call get_list separately
    in a follow-up step to verify the list contents. Never call get_list
    in the same batch as add_item calls.
    
    After assembling the list of all items, provide an estimated total cost
    based on average prices for each item in Santa Cruz, California, USA.
    If the list is empty, do not provide a cost estimate.
    If you are unsure of the cost, provide a reasonable estimate based on "typical" 
    prices for each item near the approximate area of Santa Cruz, California, USA.
"""


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


agent = Agent(
    name="shopping_list_agent",
    model=llm_model,
    instructions=SHOPPING_PROMPT,
    tools=[add_item, get_list, clear_list],
    max_turns=10,
)


if __name__ == "__main__":
    api_config = Configuration()
    # Save prompts to Orkes for future runs
    prompt_client = OrkesPromptClient(configuration=api_config)
    prompt_client.save_prompt(
        prompt_name="shopping_list_instructions",
        description="Instructions for an agent-managed shopping list with shared state.",
        prompt_template=SHOPPING_PROMPT,
        models=models)

    # AgentRuntime() reads AGENTSPAN_* env vars (default localhost), NOT the
    # CONDUCTOR_* vars. Point it at the Orkes account so deploy() reaches the
    # server, and use auth_key/auth_secret so a JWT is minted for X-Authorization.
    runtime = AgentRuntime(
        config=AgentConfig(
            server_url=server_url,
            auth_key=os.environ.get("CONDUCTOR_AUTH_KEY", None),
            auth_secret=os.environ.get("CONDUCTOR_AUTH_SECRET", None),
        )
    )

    with runtime:
        runtime.deploy(agent)
        result = runtime.run(
            agent,
            "Add milk, eggs, and bread to my shopping list, then show me the list.",
        )
        result.print_result()
