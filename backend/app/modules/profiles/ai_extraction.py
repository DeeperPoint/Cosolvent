"""Document and prose processing to structured field extraction (GAP-11).

The extraction response is constrained by a JSON Schema built from the
marketplace's own field definitions, rather than asked for in the prompt and
parsed hopefully. That matters for two reasons:

  - A ``select`` field's allowed values become an ``enum``, so an
    out-of-vocabulary value is structurally impossible instead of something the
    caller must detect and discard. Without it the model returns a plausible
    synonym, the canonical gate drops it, and the field silently fails to appear.
  - The response is JSON by construction, so an answer wrapped in prose or a
    markdown fence no longer fails the whole extraction.

Each field is returned as ``{value, confidence, source}``. The confidence and the
supporting excerpt are what let the clarify loop ask "I read this as X — right?"
rather than only "you didn't tell me Y", and they give the raw half of the
canonical ⊕ raw dual representation something per-field to point at.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.exceptions import ServiceUnavailableError
from app.modules.ai.llm_client import generate

logger = logging.getLogger("cosolvent.profiles.extraction")

# Field types that carry uploads, never extractable prose values.
_ASSET_TYPES = {"file", "files"}

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _value_schema(field: dict) -> dict[str, Any]:
    """JSON Schema for one field's value, derived from its marketplace definition."""
    ftype = (field.get("type") or "text").lower()
    options = field.get("options") or []

    if ftype == "select":
        # The enum is the whole point: it makes an invalid option unrepresentable.
        return {"type": "string", "enum": list(options)} if options else {"type": "string"}
    if ftype == "multi_select":
        item: dict[str, Any] = {"type": "string"}
        if options:
            item["enum"] = list(options)
        return {"type": "array", "items": item}
    if ftype == "number":
        return {"type": "number"}
    # text, rich_text, date, location and anything else are free strings.
    return {"type": "string"}


def build_extraction_schema(field_definitions: list[dict]) -> dict[str, Any]:
    """Build the response schema for a participant type's extractable fields.

    A submission legitimately mentions only some fields, so each one must be
    omittable. Strict schema mode does not allow that through `required`: it
    insists every key in `properties` also appears in `required`. The supported
    way to express "optional" is therefore a nullable type — each field is
    required to be *present*, but may be `null` when the text does not support
    it, and `normalize_extraction` drops those.
    """
    properties: dict[str, Any] = {}
    for field in field_definitions:
        name = field.get("name")
        if not name or (field.get("type") or "").lower() in _ASSET_TYPES:
            continue
        properties[name] = {
            # Nullable so the model can decline a field it has no evidence for.
            "type": ["object", "null"],
            "properties": {
                "value": _value_schema(field),
                "confidence": {
                    "type": "number",
                    "description": "How certain the value is (0-1), given how explicitly the text stated it.",
                },
                "source": {
                    "type": "string",
                    "description": "The excerpt of the text supporting this value; empty if none.",
                },
            },
            # Strict mode requires every property to be listed here.
            "required": ["value", "confidence", "source"],
            "additionalProperties": False,
        }

    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _strip_fence(raw: str) -> str:
    """Remove a surrounding markdown code fence, if the model added one."""
    return _FENCE_RE.sub("", raw.strip())


def _parse(raw: str) -> dict:
    try:
        parsed = json.loads(_strip_fence(raw))
    except json.JSONDecodeError as exc:
        raise ServiceUnavailableError("AI extraction returned non-JSON response") from exc
    if not isinstance(parsed, dict):
        raise ServiceUnavailableError("AI extraction returned invalid object")
    return parsed


def normalize_extraction(parsed: dict) -> dict[str, dict[str, Any]]:
    """Normalise the response to ``{field: {value, confidence, source}}``.

    Tolerates a bare ``{field: value}`` shape so a provider that ignores the
    schema still yields usable output rather than failing the request outright.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, entry in (parsed or {}).items():
        # `null` is how the schema lets the model decline a field it has no
        # evidence for — see build_extraction_schema.
        if entry is None:
            continue
        if isinstance(entry, dict) and "value" in entry:
            if entry.get("value") is None:
                continue
            confidence = entry.get("confidence")
            out[name] = {
                "value": entry.get("value"),
                # An unscored value is treated as uncertain rather than trusted.
                "confidence": float(confidence) if isinstance(confidence, (int, float)) else 0.5,
                "source": entry.get("source") or "",
            }
        else:
            out[name] = {"value": entry, "confidence": 0.5, "source": ""}
    return out


async def extract_fields_from_document(
    document_text: str,
    participant_type: str,
    field_definitions: list[dict],
) -> dict[str, dict[str, Any]]:
    """Extract profile fields from text, returning value + confidence + source per field."""
    schema = build_extraction_schema(field_definitions)
    if not schema["properties"]:
        return {}

    prompt = (
        f"Participant type: {participant_type}\n"
        "Read the text below and extract the profile fields it states or clearly implies.\n"
        "Rules:\n"
        "- Omit any field the text does not support. Do not guess.\n"
        "- For each field you return, give a confidence between 0 and 1 and quote the "
        "part of the text that supports it in `source`.\n"
        "- Where a field lists allowed values, choose one of them exactly.\n\n"
        f"Text:\n{document_text}"
    )

    raw = await generate(
        [
            {"role": "system", "content": "You extract structured data from prose."},
            {"role": "user", "content": prompt},
        ],
        use_case="document_extraction",
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "profile_fields", "strict": True, "schema": schema},
        },
    )

    normalized = normalize_extraction(_parse(raw))
    logger.info(
        "Extraction for %s returned %d field(s) from %d char(s)",
        participant_type,
        len(normalized),
        len(document_text),
    )
    return normalized
