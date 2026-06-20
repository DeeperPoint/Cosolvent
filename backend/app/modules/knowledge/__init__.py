"""Knowledge Slot — the sponsor-curated reference library.

Runtime home for CommonContext's curated domain documents: load embedded chunks into
the ``reference_library`` table and retrieve them via metadata-filtered vector search.
This is the Cosolvent side of the MarketForge ks-to-cosolvent (reference library) contract.
"""

from __future__ import annotations

from .service import load_reference_records, search_reference_library

__all__ = ["load_reference_records", "search_reference_library"]
