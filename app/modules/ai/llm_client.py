"""LLM abstraction supporting OpenAI-compatible APIs."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.modules.ai import repository as repo

logger = logging.getLogger("cosolvent.llm")


async def generate(
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Generate a response using the configured LLM."""
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
    except Exception:
        logger.error("LLM generation failed", exc_info=True)
        return "I'm sorry, I encountered an error processing your request."
