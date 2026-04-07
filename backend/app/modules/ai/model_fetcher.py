"""Dynamic model list fetching with TTL cache for multi-provider support."""

from __future__ import annotations

import logging
import re
import time

import httpx

from app.core.config import settings
from app.modules.ai.providers import PROVIDER_REGISTRY

logger = logging.getLogger("cosolvent.ai.models")

_cache: dict[str, tuple[float, list[dict]]] = {}
_CACHE_TTL = 300  # 5 minutes


def _get_api_key(provider_id: str) -> str | None:
    spec = PROVIDER_REGISTRY.get(provider_id)
    if not spec:
        return None
    return getattr(settings, spec.api_key_env_name, "") or None


async def fetch_models(provider_id: str) -> list[dict]:
    """Fetch available models for a provider with TTL caching."""
    now = time.monotonic()
    cached = _cache.get(provider_id)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    key = _get_api_key(provider_id)
    if not key:
        return []

    try:
        models = await _fetch_from_provider(provider_id, key)
        _cache[provider_id] = (now, models)
        return models
    except Exception:
        logger.warning("Failed to fetch models for %s", provider_id, exc_info=True)
        # Return stale cache if available
        if cached:
            return cached[1]
        return []


async def _fetch_from_provider(provider_id: str, api_key: str) -> list[dict]:
    if provider_id == "openai":
        return await _fetch_openai(api_key)
    elif provider_id == "openrouter":
        return await _fetch_openrouter(api_key)
    elif provider_id == "gemini":
        return await _fetch_gemini(api_key)
    return []


async def _fetch_openai(api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()

    pattern = re.compile(r"^(gpt-|o1-|o3-)")
    models = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        if pattern.match(mid):
            models.append({
                "provider": "openai",
                "model": mid,
                "description": mid,
            })
    models.sort(key=lambda x: x["model"])
    return models


async def _fetch_openrouter(api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()

    models = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        name = m.get("name", mid)
        models.append({
            "provider": "openrouter",
            "model": mid,
            "description": name,
        })
    models.sort(key=lambda x: x["model"])
    return models


async def _fetch_gemini(api_key: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        )
        resp.raise_for_status()
        data = resp.json()

    models = []
    for m in data.get("models", []):
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        # Model name comes as "models/gemini-2.0-flash" — strip the prefix
        full_name = m.get("name", "")
        mid = full_name.removeprefix("models/")
        display = m.get("displayName", mid)
        models.append({
            "provider": "gemini",
            "model": mid,
            "description": display,
        })
    models.sort(key=lambda x: x["model"])
    return models


async def validate_provider_key(provider_id: str) -> bool:
    """Try to fetch models to verify the API key works."""
    key = _get_api_key(provider_id)
    if not key:
        return False
    try:
        models = await _fetch_from_provider(provider_id, key)
        return len(models) > 0
    except Exception:
        logger.warning("Provider key validation failed for %s", provider_id, exc_info=True)
        return False
