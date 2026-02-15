"""LLM abstraction supporting OpenAI-compatible APIs."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.exceptions import ServiceUnavailableError
from app.modules.ai import repository as repo

logger = logging.getLogger("cosolvent.llm")


async def generate(
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Generate a response using the configured LLM."""
    if not settings.openai_api_key:
        raise ServiceUnavailableError("AI service unavailable: OpenAI API key not configured")

    llm_settings = await repo.get_llm_settings()
    model = "gpt-4o-mini"
    temp = temperature or 0.7
    max_tok = max_tokens or 1024

    if llm_settings:
        model = llm_settings.get("model", model)
        temp = llm_settings.get("temperature", temp)
        max_tok = llm_settings.get("max_tokens", max_tok)

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temp,
            max_tokens=max_tok,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("LLM generation failed", exc_info=True)
        raise ServiceUnavailableError("AI service unavailable: generation failed") from exc
