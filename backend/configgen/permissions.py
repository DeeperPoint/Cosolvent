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

    return {
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
