"""CLI: load a C0 synthetic population file into Cosolvent (GAP-10/9).

    python -m cli load-population population.json --mode demo
    python -m cli load-population population.json --mode production --no-index

Reads a JSON population file, enforces the synthetic watermark at the boundary
(demo mode requires a valid watermark; production rejects watermarked records),
validates each record against the marketplace profile schema, upserts synthetic
profiles idempotently by ``external_id`` and indexes them into pgvector. Requires
a running Postgres (POSTGRES_DSN / .env).
"""

from __future__ import annotations

import asyncio
from pathlib import Path


async def _run(path: Path, config_path: str, mode: str, do_index: bool):
    from app.core.database import close_db, connect_db
    from app.core.marketplace_config import load_marketplace_config
    from app.modules.population.loader import load_population_file
    from app.modules.population.service import import_population

    config = load_marketplace_config(config_path)
    await connect_db()
    try:
        records = load_population_file(path)
        return await import_population(config, records, mode=mode, do_index=do_index)  # type: ignore[arg-type]
    finally:
        await close_db()


def load_population(path: str, config_path: str, mode: str = "demo", do_index: bool = True) -> bool:
    p = Path(path)
    if not p.exists():
        print(f"File not found: {path}")
        return False
    res = asyncio.run(_run(p, config_path, mode, do_index))
    print(
        f"[ok] population import ({res.mode}): loaded={res.loaded} updated={res.updated} "
        f"indexed={res.indexed} rejected_watermark={res.rejected_watermark} "
        f"skipped_invalid={res.skipped_invalid}"
    )
    for e in res.errors[:20]:
        print(f"  - {e}")
    if len(res.errors) > 20:
        print(f"  ... and {len(res.errors) - 20} more")
    return (res.loaded + res.updated) > 0
