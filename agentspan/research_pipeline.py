#!/usr/bin/env python3
"""
Takes a topic, gathers findings, writes an article, and edits it for publication.
All in a single workflow run!
"""

# Required import to avoid pickling error from @tool in the current SDK.
# Should be resolved with this pull: https://github.com/conductor-oss/python-sdk/pull/414
import multiprocessing
multiprocessing.set_start_method("fork", force=True)

from conductor.ai.agents import (Agent, AgentRuntime, start)
from settings import settings

researcher = Agent(
    name="researcher",
    model=settings.llm_model,
    instructions=(
        "You are a researcher. Given a topic, provide key facts and data points. "
        "Be thorough but concise. Output raw research findings."
    ),
)

writer = Agent(
    name="writer",
    model=settings.llm_model,
    instructions=(
        "You are a writer. Take research findings and write a clear, engaging "
        "article. Use headers and bullet points where appropriate."
    ),
)

editor = Agent(
    name="editor",
    model=settings.llm_model,
    instructions=(
        "You are an editor. Review the article for clarity, grammar, and tone. "
        "Make improvements and output the final polished version."
    ),
)

with AgentRuntime() as runtime:
    topics = [
        "Multi-agent frameworks reshaping software development in 2026",
        "LangGraph 1.0 production deployments",
        "How much wood could a woodchuck chuck if a woodchuck could chuck wood?",
    ]
    handles = [start(researcher >> writer >> editor, t) for t in topics]
    results = [h.stream().get_result() for h in handles]
    print(*results, sep="\n\n---\n\n")