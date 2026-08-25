"""LLM abstraction supporting OpenAI-compatible APIs with multi-provider support."""

from __future__ import annotations

import logging

from app.core.exceptions import ServiceUnavailableError
from app.modules.ai import repository as repo
from app.modules.ai.client_factory import get_chat_client

logger = logging.getLogger("cosolvent.llm")


async def generate(
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
    use_case: str | None = None,
    response_format: dict | None = None,
) -> str:
    """Generate a response using the configured LLM provider.

    ``response_format`` accepts an OpenAI-style ``{"type": "json_schema", ...}`` block.
    Constraining the response with a schema — rather than asking for JSON in the prompt
    and parsing hopefully — is what makes an out-of-vocabulary value impossible instead
    of something to detect and discard afterwards.
    """
    config = await repo.get_resolved_chat_config(use_case)
    provider = config["provider"]
    model = config["model"]
    temp = temperature if temperature is not None else config["temperature"]
    max_tok = max_tokens if max_tokens is not None else config["max_tokens"]

    client = get_chat_client(provider)

    kwargs: dict = {}
    if response_format is not None:
        kwargs["response_format"] = response_format

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temp,
            max_tokens=max_tok,
            **kwargs,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("LLM generation failed (provider=%s, model=%s)", provider, model, exc_info=True)
        raise ServiceUnavailableError("AI service unavailable: generation failed") from exc
