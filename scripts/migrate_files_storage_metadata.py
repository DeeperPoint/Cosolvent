"""Backfill files.s3_key and normalize legacy privacy values.

Usage:
  uv run python scripts/migrate_files_storage_metadata.py [--dry-run] [--batch-size 200]
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

from app.core.config import settings
from app.core.database import close_db, connect_db, get_collection
from app.modules.files import storage


@dataclass
class MigrationStats:
    scanned: int = 0
    updated: int = 0
    migrated_keys: int = 0
    normalized_privacy: int = 0
    unparseable_urls: int = 0


async def _iter_files(batch_size: int):
    offset = 0
    while True:
        batch = await (
            get_collection("files")
            .find({})
            .sort("_id", 1)
            .skip(offset)
            .limit(batch_size)
            .to_list(length=batch_size)
        )
        if not batch:
            break
        for doc in batch:
            yield doc
        offset += len(batch)


def _normalized_privacy(raw_privacy: str | None) -> str:
    normalized = str(raw_privacy or "").strip().lower()
    if normalized in settings.files_allowed_privacy:
        return normalized
    return "private"


async def run_migration(dry_run: bool, batch_size: int) -> MigrationStats:
    stats = MigrationStats()
    files = get_collection("files")

    async for doc in _iter_files(batch_size):
        stats.scanned += 1
        updates: dict[str, object] = {}

        current_privacy = str(doc.get("privacy", ""))
        normalized_privacy = _normalized_privacy(doc.get("privacy"))
        if normalized_privacy != current_privacy:
            updates["privacy"] = normalized_privacy
            stats.normalized_privacy += 1

        current_key = doc.get("s3_key")
        if not (isinstance(current_key, str) and storage.is_safe_upload_key(current_key)):
            extracted = storage.extract_upload_key_from_url(str(doc.get("url", "")))
            if extracted:
                updates["s3_key"] = extracted
                stats.migrated_keys += 1
            elif doc.get("url"):
                stats.unparseable_urls += 1

        if updates:
            stats.updated += 1
            if not dry_run:
                await files.update_one({"_id": str(doc["_id"])}, {"$set": updates})

    return stats


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Backfill file storage metadata and privacy values")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing to DB")
    parser.add_argument("--batch-size", type=int, default=200, help="Number of records per read batch")
    args = parser.parse_args()

    await connect_db()
    try:
        stats = await run_migration(dry_run=args.dry_run, batch_size=max(1, args.batch_size))
    finally:
        await close_db()

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"[{mode}] scanned={stats.scanned} updated={stats.updated}")
    print(
        "details: "
        f"migrated_keys={stats.migrated_keys}, "
        f"normalized_privacy={stats.normalized_privacy}, "
        f"unparseable_urls={stats.unparseable_urls}"
    )
    if stats.unparseable_urls:
        print("warning: unparseable URLs were left unchanged and should be reviewed manually.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
