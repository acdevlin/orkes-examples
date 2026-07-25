#!/usr/bin/env python3
"""Agent with tools — define a tool function, agent calls it."""

# Required import to avoid pickling error from @tool in the current SDK.
# Should be resolved with this pull: https://github.com/conductor-oss/python-sdk/pull/414
import multiprocessing
multiprocessing.set_start_method("fork", force=True)

from conductor.ai.agents import Agent, AgentRuntime, tool
from settings import settings

@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"72°F and sunny in {city}"

instruction: str = ("You are an outdoor activity assistant."
" When asked about a city, look up the weather there, then recommend 2-3 specific" 
" outdoor activities suited to those conditions. Be direct: good weather for hiking"
" is different from good weather for a beach day."
)

agent = Agent(
    name="weatherbot",
    model=settings.llm_model,
    instructions=instruction,
    tools=[get_weather],
)

with AgentRuntime() as runtime:
    print(f"Using model: {settings.llm_model}")
    result = runtime.run(agent, "What should I do today in San Francisco?")
    result.print_result()