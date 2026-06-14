"""Pluggable LLM layer for the optional enrichment / repair stages.

The deterministic pipeline runs with no LLM. When ``--enrich`` / ``--llm-repair`` are
requested, an ``LLMClient`` is used. ``OpenRouterClient`` mirrors the call pattern in
CommonContext's ``schema_analyzer.py``. Tests inject a stub client, so nothing here is
required for offline runs.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Protocol

_PROMPTS = Path(__file__).parent / "prompts"
_DEFAULT_MODEL = "google/gemini-2.5-flash"
_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str: ...


# .env files searched for OPENROUTER_API_KEY when it isn't already in the environment.
_ENV_CANDIDATES = [
    Path(__file__).resolve().parents[2] / ".env",   # Cosolvent/.env
    Path(__file__).resolve().parents[3] / "CommonContext" / ".env",
]


def _discover_api_key() -> str | None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    for env_path in _ENV_CANDIDATES:
        if not env_path.exists():
            continue
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


class OpenRouterClient:
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.environ.get("OPENROUTER_MODEL", _DEFAULT_MODEL)
        self.api_key = api_key or _discover_api_key()
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not found (env or Cosolvent/.env). Required for --enrich."
            )

    def complete(self, system: str, user: str) -> str:
        import httpx  # imported lazily so offline runs never need it

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://deeperpoint.com",
            "X-Title": "MarketForge Config Generator",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 8000,
        }
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"No response from OpenRouter: {json.dumps(data)[:500]}")
        return choices[0].get("message", {}).get("content", "")


def load_prompt(name: str) -> str:
    return (_PROMPTS / name).read_text()


def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of a possibly fenced LLM response."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    blob = fenced.group(1).strip() if fenced else text.strip()
    start = min((i for i in (blob.find("{"), blob.find("[")) if i != -1), default=-1)
    if start > 0:
        blob = blob[start:]
    return json.loads(blob)


def make_llm_repair(client: LLMClient) -> Callable[[dict[str, Any], list[dict]], dict[str, Any]]:
    """Return a repair callable for ``validate.validate_and_repair``.

    Given the failing draft + Pydantic errors, ask the model to return a corrected
    config JSON. The corrected draft is re-validated by the loop, so a bad fix just
    costs another round rather than producing invalid output.
    """
    system = load_prompt("repair.md")

    def _repair(draft: dict[str, Any], errors: list[dict]) -> dict[str, Any]:
        user = (
            "Current config (JSON):\n"
            + json.dumps(draft, indent=2)
            + "\n\nValidation errors:\n"
            + json.dumps(errors, indent=2)
            + "\n\nReturn the corrected config as a single JSON object."
        )
        out = client.complete(system, user)
        fixed = extract_json(out)
        return fixed if isinstance(fixed, dict) else draft

    return _repair
