#!/usr/bin/env python3
""" 
Guardrails validate agent input or output. On failure, you choose how to respond: 
retry with feedback, raise an error, auto-fix, or escalate to a human. 
"""

# Required import to avoid pickling error from @tool in the current SDK.
# Should be resolved with this pull: https://github.com/conductor-oss/python-sdk/pull/414
import multiprocessing
multiprocessing.set_start_method("fork", force=True)

from conductor.ai.agents import (
    Agent, 
    AgentRuntime, 
    Guardrail, 
    GuardrailResult, 
    guardrail,
    OnFail
)

from settings import settings
from typing import Final

WORD_LIMIT: Final[int] = 500
GUARD_WORD_LIMIT_MESSAGE: Final[str] = f"Please provide a more concise answer of under {WORD_LIMIT} words."

@guardrail
def word_limit(content: str) -> GuardrailResult:
    """Keeps responses concise."""
    if len(content.split()) > WORD_LIMIT:
        return GuardrailResult(passed=False, message=GUARD_WORD_LIMIT_MESSAGE)
    return GuardrailResult(passed=True)

agent = Agent(
    name="concise_bot",
    model=settings.llm_model,
    guardrails=[Guardrail(word_limit, on_fail=OnFail.RETRY)],
)

with AgentRuntime() as runtime:
    print(f"Using model: {settings.llm_model}")
    result = runtime.run(agent, "Explain quantum computing.")
    result.print_result()
