"""Constrained agent fill pass for AGENT_FILL markers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from .agent_markers import apply_marker_replacements, find_fill_markers
from .agent_prompt import build_fill_prompt, prompt_hash
from .ir import FrontendIR

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
AGENT_FILL_PREFIXES = (
    "src/app/",
    "src/components/layouts/",
    "src/components/forms/",
    "src/components/shared/",
)


@dataclass(frozen=True)
class AgentFillOptions:
    enabled: bool = False
    model: str = "anthropic/claude-3.5-sonnet"
    timeout_seconds: int = 120


@dataclass(frozen=True)
class AgentFillResult:
    artifacts: dict[str, str]
    filled_files: list[str]
    prompt_hash: str | None


def run_agent_fill(
    artifacts: dict[str, str],
    ir: FrontendIR,
    options: AgentFillOptions,
    *,
    feedback: str | None = None,
) -> AgentFillResult:
    """Run second-pass marker fill over eligible artifacts."""
    if not options.enabled:
        return AgentFillResult(dict(artifacts), [], None)

    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required when --agent-fill is enabled")

    updated = dict(artifacts)
    filled: list[str] = []
    prompt_hashes: list[str] = []

    for path in sorted(updated):
        if not _eligible_for_fill(path):
            continue
        content = updated[path]
        markers = find_fill_markers(content)
        if not markers:
            continue

        marker_ids = [m.marker_id for m in markers]
        prompt = build_fill_prompt(
            file_path=path,
            file_content=content,
            marker_ids=marker_ids,
            ir=ir,
            feedback=feedback,
        )
        prompt_hashes.append(prompt_hash(prompt))
        response_text = _call_openrouter(
            prompt=prompt,
            model=options.model,
            api_key=api_key,
            timeout=options.timeout_seconds,
        )
        parsed = _parse_response_json(response_text)
        replacements = {
            str(item["id"]): str(item["content"])
            for item in parsed.get("replacements", [])
            if isinstance(item, dict) and "id" in item and "content" in item
        }
        updated[path] = apply_marker_replacements(content, replacements)
        filled.append(path)

    combined_hash = None
    if prompt_hashes:
        combined_hash = prompt_hash("\n".join(sorted(prompt_hashes)))
    return AgentFillResult(updated, sorted(filled), combined_hash)


def _eligible_for_fill(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in AGENT_FILL_PREFIXES)


def _call_openrouter(*, prompt: str, model: str, api_key: str, timeout: int) -> str:
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urlrequest.Request(
        OPENROUTER_CHAT_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except urlerror.HTTPError as exc:  # pragma: no cover - network path
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ValueError(f"OpenRouter HTTP {exc.code}: {detail[:500]}") from exc
    except urlerror.URLError as exc:  # pragma: no cover - network path
        raise ValueError(f"OpenRouter request failed: {exc}") from exc

    content = (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    if not isinstance(content, str) or not content.strip():
        raise ValueError("OpenRouter returned empty content for agent fill")
    return content


def _parse_response_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Agent fill response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Agent fill response must be a JSON object")
    if "replacements" not in parsed:
        raise ValueError("Agent fill response missing 'replacements'")
    if not isinstance(parsed["replacements"], list):
        raise ValueError("'replacements' must be a list")
    return parsed
