# Copyright (c) 2025 Agentspan
# Licensed under the MIT License. See LICENSE file in the project root for details.

"""Shared settings for all examples.

Set ``AGENTSPAN_LLM_MODEL`` as an environment variable to override the
default model used by all examples::

    export AGENTSPAN_LLM_MODEL=anthropic/claude-sonnet-4-20250514
    export AGENTSPAN_LLM_MODEL=google_gemini/gemini-2.0-flash

If unset, defaults to ``anthropic/claude-sonnet-4-6``.

``AGENTSPAN_SECONDARY_LLM_MODEL`` provides a second model for multi-model examples
(e.g., cheap triage vs capable specialist). Defaults to ``openai/gpt-4o``.
"""

import os
from dataclasses import dataclass

@dataclass
class Settings:
    # Google Gemini model reference can be found here: 
    # https://ai.google.dev/gemini-api/docs/latest-model
    llm_model: str = os.environ.get("AGENTSPAN_LLM_MODEL", "google_gemini/gemini-3.1-flash-lite")
    secondary_llm_model: str = os.environ.get("AGENTSPAN_SECONDARY_LLM_MODEL", "openai/gpt-4o")
    api_key: str = os.environ.get("GEMINI_API_KEY", None)
    gcp_project: str = os.environ.get("GOOGLE_CLOUD_PROJECT", None)

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_model=cls.llm_model,
            secondary_llm_model=cls.secondary_llm_model,
            api_key=cls.api_key,
            gcp_project=cls.gcp_project,
        )


settings = Settings.from_env()