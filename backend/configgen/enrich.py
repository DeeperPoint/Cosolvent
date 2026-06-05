"""LLM enrichment pass: refine field visibility, select-vs-multi, and labels.

Runs AFTER the deterministic assemble and BEFORE validation. For safety the LLM is
**not** allowed to rewrite the config — it returns a flat list of per-field
*adjustments*, which are applied here through a strict whitelist (only ``visibility``,
``label``, and a ``select``↔``multi_select`` type swap). Field names, options, slugs,
permissions, and structure are never touched, so provenance survives and the result
still validates. The validate-repair loop runs afterwards as a backstop.
"""

from __future__ import annotations

from typing import Any

from .llm import LLMClient, extract_json, load_prompt

_VALID_VISIBILITY = {"public", "protected", "private"}
_SWAPPABLE_TYPES = {"select", "multi_select"}


def _index_fields(draft: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Map (participant_slug, field_name) -> the field dict, for in-place edits."""
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for slug, schema in draft.get("profile_schemas", {}).items():
        for section in schema.get("sections", []):
            for field in section.get("fields", []):
                index[(slug, field.get("name"))] = field
    return index


def _field_summary(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Compact, LLM-friendly view of every field that's a candidate for adjustment."""
    rows: list[dict[str, Any]] = []
    for slug, schema in draft.get("profile_schemas", {}).items():
        for section in schema.get("sections", []):
            for field in section.get("fields", []):
                rows.append({
                    "participant": slug,
                    "name": field.get("name"),
                    "label": field.get("label"),
                    "type": field.get("type"),
                    "visibility": field.get("visibility"),
                    "n_options": len(field.get("options", []) or []),
                })
    return rows


def enrich_fields(client: LLMClient, draft: dict[str, Any]) -> dict[str, Any]:
    """Ask the LLM for field adjustments and apply the whitelisted ones in place."""
    system = load_prompt("enrich.md")
    user = (
        "Fields to review (JSON):\n"
        + __import__("json").dumps(_field_summary(draft), indent=2)
        + '\n\nReturn ONLY a JSON array of adjustments, each like:\n'
        '{"participant": "...", "name": "...", '
        '"visibility": "public|protected|private", '
        '"type": "select|multi_select", "label": "..."}\n'
        "Include a field only if you are changing something. Omit keys you are not changing."
    )

    try:
        raw = client.complete(system, user)
        adjustments = extract_json(raw)
    except Exception:
        # API error or malformed response → keep the deterministic draft unchanged.
        return draft
    if not isinstance(adjustments, list):
        return draft

    index = _index_fields(draft)
    for adj in adjustments:
        if not isinstance(adj, dict):
            continue
        key = (adj.get("participant"), adj.get("name"))
        field = index.get(key)
        if field is None:
            continue

        vis = adj.get("visibility")
        if vis in _VALID_VISIBILITY:
            # Files only support public/private; collapse protected -> private.
            if field.get("type") in ("file", "files") and vis == "protected":
                vis = "private"
            field["visibility"] = vis

        new_type = adj.get("type")
        # Only allow a select<->multi_select swap (both already carry options).
        if new_type in _SWAPPABLE_TYPES and field.get("type") in _SWAPPABLE_TYPES:
            field["type"] = new_type

        label = adj.get("label")
        if isinstance(label, str) and label.strip():
            field["label"] = label.strip()

    return draft
