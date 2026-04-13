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
) -> str:
    """Generate a response using the configured LLM provider."""
    config = await repo.get_resolved_chat_config(use_case)
    provider = config["provider"]
    model = config["model"]
    temp = temperature if temperature is not None else config["temperature"]
    max_tok = max_tokens if max_tokens is not None else config["max_tokens"]

    client = get_chat_client(provider)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temp,
            max_tokens=max_tok,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("LLM generation failed (provider=%s, model=%s)", provider, model, exc_info=True)
        raise ServiceUnavailableError("AI service unavailable: generation failed") from exc
