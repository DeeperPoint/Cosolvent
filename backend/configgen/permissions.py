"""Deterministic rules: participant role-kind -> permissions, communication, discovery.

These encode the conventions visible in Cosolvent's hand-written marketplace.yaml, but
emit the *model-valid* shape (e.g. ``can_search`` is a bool per ``ParticipantPermissions``,
not the list form the committed example file drifted to).
"""

from __future__ import annotations

from .ir import MarketDefinition, ParticipantDef, RoleKind

# Role-kind -> the 8 permission booleans expected by ParticipantPermissions.
#   supply / facilitator  -> listed, found in search, receive contact (passive side)
#   demand                -> searches and initiates (active side)
_PERMISSIONS: dict[RoleKind, dict[str, bool]] = {
    "supply": {
        "can_list": True,
        "can_search": False,
        "can_initiate_conversation": False,
        "can_receive_conversation": True,
        "can_share_private_assets": True,
        "requires_onboarding": True,
        "requires_approval": True,
        "visible_in_search": True,
    },
    "demand": {
        "can_list": False,
        "can_search": True,
        "can_initiate_conversation": True,
        "can_receive_conversation": True,
        "can_share_private_assets": False,
        "requires_onboarding": True,
        "requires_approval": True,
        "visible_in_search": False,
    },
    "facilitator": {
        "can_list": True,
        "can_search": False,
        "can_initiate_conversation": False,
        "can_receive_conversation": True,
        "can_share_private_assets": True,
        "requires_onboarding": True,
        "requires_approval": True,
        "visible_in_search": True,
    },
}


def permissions_for(role: RoleKind) -> dict[str, bool]:
    return dict(_PERMISSIONS[role])


def onboarding_for(role: RoleKind) -> dict:
    """Supply/facilitator do doc-driven AI onboarding; demand is lighter."""
    if role == "demand":
        return {
            "requires_approval": True,
            "approval_type": "manual",
            "document_upload_required": False,
            "ai_extraction_enabled": False,
            "ai_profile_generation": False,
            "welcome_email_on_approval": True,
            "profile_completeness_threshold": 70,
        }
    return {
        "requires_approval": True,
        "approval_type": "manual",
        "document_upload_required": True,
        "ai_extraction_enabled": True,
        "ai_profile_generation": True,
        "welcome_email_on_approval": True,
        "profile_completeness_threshold": 80,
    }


def conversation_rules(participants: list[ParticipantDef]) -> list[dict]:
    """A rule for every ordered (initiator, receiver) pair where the permission
    matrix says the initiator can initiate and the receiver can receive."""
    rules: list[dict] = []
    for a in participants:
        if not _PERMISSIONS[a.role]["can_initiate_conversation"]:
            continue
        for b in participants:
            if a.slug == b.slug:
                continue
            if _PERMISSIONS[b.role]["can_receive_conversation"]:
                rules.append({"initiator": a.slug, "receiver": b.slug, "requires_approval": True})
    return rules


def discovery_block(market: MarketDefinition) -> dict:
    """searchable_types = visible-in-search types; filter_fields = searchable
    select/multi_select fields that actually exist in some profile schema."""
    searchable_types = [p.slug for p in market.participants if _PERMISSIONS[p.role]["visible_in_search"]]

    filter_fields: list[str] = []
    seen: set[str] = set()
    for p in market.participants:
        for sec in p.sections:
            for f in sec.fields:
                if f.searchable and f.type in ("select", "multi_select") and f.name not in seen:
                    seen.add(f.name)
                    filter_fields.append(f.name)
    filter_fields = filter_fields[:8]

    block: dict = {
        "searchable_types": searchable_types,
        "filter_fields": filter_fields,
        "result_visibility": {"anonymous": "public", "authenticated": "protected"},
        "access": {"anonymous_search_enabled": True, "anonymous_filter_mode": "public_only"},
        "ai": {
            "vector_search_enabled": True,
            "rag_query_enabled": True,
            "follow_up_suggestions": True,
            "profile_retrieval_mode": "hybrid",
            "rag_failure_behavior": "empty",
            "profile_similarity_threshold": 0.25,
            "max_vector_candidates": 500,
        },
    }
    matching = _matching_block(market)
    if matching:
        block["matching"] = matching
    return block


def _matching_block(market: MarketDefinition) -> dict | None:
    """GAP-3: config-driven weighted-slot scoring for principal↔principal matching.

    Deterministically derives per-target weight tables from the searchable select /
    multi_select fields the principal types share: multi_select → jaccard (weighted higher),
    select → scalar_eq. ``vector_weight`` takes the remainder so weights sum to 1.0. Hard gates
    are policy (not inferable), so they are carried from the domain schema's ``matching.hard_gates``
    (keyed by target slug or role) rather than guessed.
    """
    principals = [p for p in market.participants if p.role in ("supply", "demand")]
    if len(principals) < 2:
        return None

    gates_by_key = (market.matching or {}).get("hard_gates", {}) or {}

    def _gates_for(p: "ParticipantDef") -> list[dict]:
        raw = gates_by_key.get(p.slug) or gates_by_key.get(p.role) or []
        out = []
        for g in raw if isinstance(raw, list) else []:
            if isinstance(g, dict) and g.get("name") and g.get("field") and g.get("op"):
                gate = {"name": g["name"], "field": g["field"], "op": g["op"]}
                if "value" in g:
                    gate["value"] = g["value"]
                out.append(gate)
        return out

    ftype: dict[str, str] = {}
    per_type: list[set[str]] = []
    for p in principals:
        names: set[str] = set()
        for sec in p.sections:
            for f in sec.fields:
                if f.searchable and f.type in ("select", "multi_select"):
                    ftype[f.name] = f.type
                    names.add(f.name)
        per_type.append(names)
    common = sorted(set.intersection(*per_type)) if per_type else []
    if not common:
        return None

    base = {n: (2.0 if ftype[n] == "multi_select" else 1.0) for n in common}
    total_base = sum(base.values())
    slot_budget = 0.5  # slots share half the weight; semantic similarity keeps the rest

    def _profile(p: "ParticipantDef") -> dict:
        slots = []
        acc = 0.0
        for n in common:
            w = round(slot_budget * base[n] / total_base, 3)
            acc += w
            slots.append({
                "name": f"{n}_fit",
                "fields": [n],
                "comparator": "jaccard" if ftype[n] == "multi_select" else "scalar_eq",
                "weight": w,
            })
        prof: dict = {"vector_weight": round(1.0 - acc, 6), "slots": slots}
        gates = _gates_for(p)
        if gates:
            prof["hard_gates"] = gates
        return prof

    return {"per_target": {p.slug: _profile(p) for p in principals}}
