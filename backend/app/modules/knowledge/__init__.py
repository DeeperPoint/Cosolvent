"""Knowledge Slot — the sponsor-curated reference library.

Runtime home for CommonContext's curated domain documents: load embedded chunks into
the ``reference_library`` table and retrieve them via metadata-filtered vector search.
This is the Cosolvent side of the MarketForge ks-to-cosolvent (reference library) contract.
"""

from __future__ import annotations

from .service import (
    active_escape_hatches,
    create_escape_hatch,
    list_escape_hatches,
    list_gap_signals,
    load_reference_records,
    maybe_record_gate_gap,
    maybe_record_query_gap,
    record_gap_signal,
    search_reference_library,
    set_escape_hatch_status,
    set_gap_status,
)

__all__ = [
    "active_escape_hatches",
    "create_escape_hatch",
    "list_escape_hatches",
    "list_gap_signals",
    "load_reference_records",
    "maybe_record_gate_gap",
    "maybe_record_query_gap",
    "record_gap_signal",
    "search_reference_library",
    "set_escape_hatch_status",
    "set_gap_status",
]
