"""CLI: stamp a raw population file with synthetic watermarks (GAP-9 reference signer).

    python -m cli stamp-population raw.json -o population.json

This is the reference implementation of the watermark ClientSynth attaches to its
exported synthetic records. It reads a population file whose records have
``participant_type`` / ``external_id`` / ``fields`` and writes a copy with a valid
``_watermark`` on each, signed with the shared secret (synthetic_watermark_secret).
No database required.
"""

from __future__ import annotations

import json
from pathlib import Path


def stamp_population(in_path: str, out_path: str, secret: str | None = None) -> bool:
    from app.core import watermark
    from app.core.config import settings
    from app.modules.population.loader import load_population_file

    key = secret or settings.synthetic_watermark_secret
    records = load_population_file(in_path)
    stamped = [watermark.stamp(r, key) if isinstance(r, dict) else r for r in records]
    Path(out_path).write_text(json.dumps(stamped, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] stamped {len(stamped)} record(s) -> {out_path}")
    return True
