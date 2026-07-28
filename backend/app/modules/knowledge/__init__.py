"""Knowledge Slot — the sponsor-curated reference library.

Runtime home for CommonContext's curated domain documents: load embedded chunks into
the ``reference_library`` table and retrieve them via metadata-filtered vector search.
This is the Cosolvent side of the MarketForge ks-to-cosolvent (reference library) contract.
"""

from __future__ import annotations

from .service import (
    list_gap_signals,
    load_reference_records,
    maybe_record_query_gap,
    record_gap_signal,
    search_reference_library,
    set_gap_status,
)

__all__ = [
    "list_gap_signals",
    "load_reference_records",
    "maybe_record_query_gap",
    "record_gap_signal",
    "search_reference_library",
    "set_gap_status",
]
