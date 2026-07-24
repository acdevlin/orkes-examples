#!/usr/bin/env python3
"""Agent with tools — define a tool function, agent calls it."""

# Required import to avoid pickling error from @tool in the current SDK.
import multiprocessing
multiprocessing.set_start_method("fork", force=True)

from conductor.ai.agents import Agent, AgentRuntime, tool
from settings import settings

@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"72°F and sunny in {city}"

agent = Agent(
    name="weatherbot",
    model=settings.llm_model,
    instructions="You are an outdoor activity assistant. When asked about a city, look up the weather there, then recommend 2-3 specific outdoor activities suited to those conditions. Be direct: good weather for hiking is different from good weather for a beach day.",
    tools=[get_weather],
)

with AgentRuntime() as runtime:
    result = runtime.run(agent, "What should I do today in San Francisco?")
    result.print_result()