"""Configure OpenRouter embeddings and (re)index all active profiles for vector matching.

    OPENROUTER_API_KEY=... POSTGRES_DSN=postgresql+asyncpg://postgres:postgres@localhost:15432/cosolvent \
    MARKETPLACE_CONFIG_PATH=../marketplace.yaml .venv/bin/python scripts/enable_embeddings.py
"""
import asyncio
import os

from app.core.database import connect_db, close_db, get_collection
from app.core.marketplace_config import load_marketplace_config, set_marketplace_config

CFG = load_marketplace_config(os.environ.get("MARKETPLACE_CONFIG_PATH", "../marketplace.yaml"))

EMBED = {
    "embedding_provider": "openrouter",
    "embedding_model": "openai/text-embedding-3-small",
    "embedding_dimensions": 1536,
}


async def main():
    await connect_db()
    set_marketplace_config(CFG)

    # 1) Persist embedding config into ai_llm_settings.
    col = get_collection("ai_llm_settings")
    s = await col.find_one({})
    if s:
        await col.find_one_and_update({"_id": s["_id"]}, {"$set": EMBED})
    else:
        await col.insert_one({**EMBED})
    print(f"[config] embeddings → {EMBED['embedding_provider']} / {EMBED['embedding_model']}")

    # 2) Verify a live embedding call before doing bulk work.
    from app.modules.ai.embedding_client import get_embedding
    try:
        v = await get_embedding("machinery seller caterpillar excavator new")
        print(f"[test]   OpenRouter embedding OK — {len(v)} dims")
    except Exception as exc:
        print(f"[test]   FAILED — OpenRouter embeddings not available: {exc}")
        await close_db()
        return 1

    # 3) Re-index every active profile.
    from app.modules.discovery.indexer import index_profile
    profiles = await get_collection("profiles").find({"status": "active"}).to_list(length=100000)
    ok = 0
    for i, p in enumerate(profiles, 1):
        p.setdefault("_id", p.get("id"))
        try:
            await index_profile(p, CFG)
            ok += 1
        except Exception as exc:
            print(f"  ! index failed for {p.get('_id')}: {exc}")
        if i % 20 == 0:
            print(f"  …{i}/{len(profiles)} indexed")
    print(f"[index]  {ok}/{len(profiles)} active profiles embedded")

    # profile_vectors is a real table (not a document collection) — count it directly.
    from sqlalchemy import text as _sql
    from app.core.database import session_scope
    async with session_scope() as sess:
        n = (await sess.execute(_sql("SELECT count(*) FROM profile_vectors"))).scalar_one()
    print(f"[done]   profile_vectors now holds {n} vectors")
    await close_db()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
