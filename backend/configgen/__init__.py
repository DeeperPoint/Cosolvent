"""configgen — generate a Cosolvent ``marketplace.yaml`` from a CommonContext domain schema.

This is the MarketForge "Domain schema -> marketplace.yaml generator" connector
(Forge ROADMAP §7). It imports Cosolvent's real ``MarketplaceConfig`` as its acceptance
oracle, so emitted configs are guaranteed to validate (and therefore compile).
"""

from __future__ import annotations

from .generate import GenerationResult, generate_from_schema

__all__ = ["generate_from_schema", "GenerationResult"]
