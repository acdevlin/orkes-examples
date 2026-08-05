"""
Shared utilities across all agents.
"""

from conductor.client.http.models.prompt_template import PromptTemplate
from conductor.client.orkes.orkes_prompt_client import OrkesPromptClient


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
            "Confirm CONDUCTOR_SERVER_URL and your auth key/secret are correct."
            f"Full error: {err}"
        ) from err
    prompt = prompt_client.get_prompt(prompt_name)
    if prompt is None:
        raise RuntimeError(
            f"Prompt template '{prompt_name}' was saved but could not be read back. "
            "This likely indicates a server-side permissions or propagation issue."
        )
    return prompt
