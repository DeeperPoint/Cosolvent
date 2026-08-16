"""CLI: publish a participant type's profile schema as a JSON descriptor.

    python -m cli export-profile-schema producer -o producer.schema.json

Cosolvent owns the marketplace configuration, so it publishes the contract that
generators code against rather than having them parse ``marketplace.yaml``.
ClientSynth feeds this descriptor to its population exporter to coerce and
validate records *before* shipping them, so schema violations surface at
generation time instead of as rejections at the ingest boundary (GAP-10).

The descriptor deliberately carries only what a generator needs: field names,
types, whether they are required, and the allowed options for select fields.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_profile_schema_descriptor(config: Any, participant_type: str) -> dict[str, Any]:
    schema = config.profile_schemas.get(participant_type)
    if schema is None:
        available = ", ".join(sorted(config.profile_schemas)) or "(none)"
        raise ValueError(f"no profile schema for participant type '{participant_type}'. Available: {available}")

    fields = []
    for field in schema.all_fields:
        entry: dict[str, Any] = {"name": field.name, "type": field.type, "required": field.required}
        if field.options:
            entry["options"] = list(field.options)
        fields.append(entry)

    return {"participantType": participant_type, "fields": fields}


def export_profile_schema(participant_type: str, config_path: str, out_path: str | None) -> bool:
    from app.core.marketplace_config import load_marketplace_config

    config = load_marketplace_config(config_path)
    try:
        descriptor = build_profile_schema_descriptor(config, participant_type)
    except ValueError as exc:
        print(f"[error] {exc}")
        return False

    text = json.dumps(descriptor, indent=2, ensure_ascii=False)
    if out_path:
        Path(out_path).write_text(text, encoding="utf-8")
        print(f"[ok] wrote profile schema for '{participant_type}' ({len(descriptor['fields'])} field(s)) -> {out_path}")
    else:
        print(text)
    return True
