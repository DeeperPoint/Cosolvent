"""Market-dynamics reporting — the missing 'simulation runner + analytics' piece
(roadmap Track B item B1.8 'Market Physics Scorecard'; CONVERGENCE.md Phase 6
activity 7). `get_market_overview` is aggregate-only, computed from data the engine
already persists in `profiles` / `deals` / `story_versions` — no new tables, no
background jobs. `get_match_density` is the exception: no match is ever persisted,
so it runs live (capped) pgvector queries — see its docstring for the tradeoff.
"""

from __future__ import annotations

from .service import get_market_overview, get_match_density

__all__ = ["get_market_overview", "get_match_density"]
