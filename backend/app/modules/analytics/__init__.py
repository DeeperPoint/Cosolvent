"""Market-dynamics reporting — the missing 'simulation runner + analytics' piece
(roadmap Track B item B1.8 'Market Physics Scorecard'; CONVERGENCE.md Phase 6
activity 7). Aggregate-only, computed from data the engine already persists in
`profiles` / `deals` / `story_versions`. No new tables, no background jobs.
"""

from __future__ import annotations

from .service import get_market_overview

__all__ = ["get_market_overview"]
