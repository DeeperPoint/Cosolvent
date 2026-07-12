"""Content-hash identity for story versions (Story Progression integrity rule 2).

A story version is identified by the hash of its *content* — disclosure level, narrative,
and structured parameter snapshot. Acknowledgments pin to this hash, so a party can never
"acknowledge a moving target": if the content changes, the hash changes and prior
acknowledgments no longer apply.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def content_hash(disclosure_level: str, narrative: str, snapshot: dict[str, Any]) -> str:
    """Deterministic SHA-256 over the canonical (sorted, compact) content representation."""
    canonical = json.dumps(
        {
            "disclosure_level": disclosure_level,
            "narrative": narrative,
            "snapshot": snapshot,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
