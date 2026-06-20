"""CLI: load a CommonContext reference-library export into Cosolvent.

    python -m cli load-references refs.jsonl --vertical machinery_trade

Reads a JSONL file of ingestion records (one per line) and bulk-loads them into the
``reference_library`` table. Idempotent per source document. Requires a running
Postgres (the same DB the app uses) — connection comes from POSTGRES_DSN / .env.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            # tolerate a stray non-JSON line rather than aborting a large file
            continue
    return records


async def _run(path: Path, vertical: str | None) -> dict:
    from app.core.database import close_db, connect_db
    from app.modules.knowledge import load_reference_records

    await connect_db()
    try:
        records = _read_jsonl(path)
        return await load_reference_records(records, default_vertical=vertical)
    finally:
        await close_db()


def load_references_file(path: str, vertical: str | None = None) -> bool:
    p = Path(path)
    if not p.exists():
        print(f"File not found: {path}")
        return False
    result = asyncio.run(_run(p, vertical))
    print(
        f"✓ Loaded {result['loaded']} chunk(s) across {result['documents']} document(s) "
        f"into reference_library"
        + (f" (skipped {result['skipped']} malformed)" if result["skipped"] else "")
    )
    return result["loaded"] > 0
