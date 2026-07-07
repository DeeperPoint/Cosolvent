"""Deals service: the collaborative deal record + Deal Brief (Handoff Artifact).

Aligned with the repo's stated direction (see DealStateDiagram.mmd): the Deal Brief is a
*collaborative record* of a deal's moving parts (principals, parameters, facilitators,
documents, context) — NOT an automated negotiation engine. Lifecycle:

    draft → active → agreed → brief_ready → handoff        (+ cancelled)

``agreed`` is computed: every principal has agreed AND no facilitator slot is still "needed".
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError, ServiceUnavailableError
from app.core.marketplace_config import MarketplaceConfig
from app.modules.deals import repository as repo

logger = logging.getLogger("cosolvent.deals.service")

TERMINAL_STATUSES = {"handoff", "cancelled"}


# ── Creation ─────────────────────────────────────────────────────────────────
async def create_deal(user: dict[str, Any], body: Any, config: MarketplaceConfig) -> dict[str, Any]:
    """Create a deal from a conversation (preferred) or directly with a counterparty."""
    principals: list[dict[str, Any]]
    conversation_id: str | None = None

    if body.conversation_id:
        from app.modules.communication import repository as comms_repo

        conv = await comms_repo.get_conversation(body.conversation_id)
        if not conv:
            raise NotFoundError("Conversation not found")
        if user["_id"] not in [p["user_id"] for p in conv.get("participants", [])]:
            raise ForbiddenError("Not a participant in this conversation")
        conversation_id = str(conv["_id"])
        principals = [_principal(p["user_id"], p.get("participant_type", ""), config)
                      for p in conv["participants"]]
    elif body.counterparty_user_id:
        from app.modules.auth.repository import find_user_by_id

        other = await find_user_by_id(body.counterparty_user_id)
        if not other:
            raise NotFoundError("Counterparty not found")
        principals = [
            _principal(user["_id"], user.get("participant_type", ""), config),
            _principal(other["_id"], other.get("participant_type", ""), config),
        ]
    else:
        raise AppError("Provide either conversation_id or counterparty_user_id", 400)

    participants = _members_from_principals(principals)
    doc = {
        "status": "draft",
        "vertical": _vertical(config),
        "conversation_id": conversation_id,
        "principals": principals,
        # Membership index (array-of-objects) used for listing + permission checks.
        "participants": participants,
        "facilitator_slots": _facilitator_slots(config),
        "parameters": [],
        "documents": [],
        "context": body.context or "",
        "brief": None,
        "created_by": user["_id"],
    }
    deal = await repo.create_deal(doc)
    await _notify([m["user_id"] for m in participants], exclude=user["_id"], ntype="deal_created",
                  data={"deal_id": str(deal["_id"])})
    return _serialize(deal)


# ── Reads ──────────────────────────────────────────────────────────────────
async def list_deals(user: dict[str, Any]) -> list[dict[str, Any]]:
    return [_serialize(d) for d in await repo.list_deals_for_user(user["_id"])]


async def get_deal(deal_id: str, user: dict[str, Any]) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_party(deal, user["_id"])
    return _serialize(deal)


# ── Mutations ────────────────────────────────────────────────────────────────
async def update_context(deal_id: str, user: dict[str, Any], context: str | None) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    _assert_not_terminal(deal)
    updated = await repo.update_deal(deal_id, {"context": context or "", "status": _advance(deal)})
    return _serialize(updated)


async def upsert_parameter(deal_id: str, user: dict[str, Any], param: Any) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    _assert_not_terminal(deal)

    params = list(deal.get("parameters", []))
    existing = next((p for p in params if p.get("key") == param.key), None)
    incoming = {
        "key": param.key,
        "label": param.label,
        "value": param.value,
        "unit": param.unit,
        "agreed": bool(param.agreed) if param.agreed is not None else False,
        "note": param.note,
    }
    if existing:
        # Update only provided fields, preserve the rest.
        for k in ("label", "value", "unit", "note"):
            if getattr(param, k) is not None:
                existing[k] = getattr(param, k)
        if param.agreed is not None:
            existing["agreed"] = bool(param.agreed)
    else:
        params.append(incoming)

    updated = await repo.update_deal(deal_id, {"parameters": params, "status": _advance(deal)})
    return _serialize(updated)


async def set_facilitator(deal_id: str, user: dict[str, Any], req: Any) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    _assert_not_terminal(deal)

    slots = list(deal.get("facilitator_slots", []))
    slot = next((s for s in slots if s.get("role_type") == req.role_type), None)
    if slot is None:
        slot = {"role_type": req.role_type, "status": "needed", "user_id": None, "note": None}
        slots.append(slot)
    slot["status"] = req.status
    if req.user_id is not None:
        slot["user_id"] = req.user_id
    if req.note is not None:
        slot["note"] = req.note

    # A confirmed facilitator with an assigned user joins the deal's membership index.
    members = list(deal.get("participants", []))
    if slot.get("user_id") and slot["user_id"] not in [m["user_id"] for m in members]:
        members.append({"user_id": slot["user_id"], "role": "facilitator"})

    patched = {**deal, "facilitator_slots": slots, "participants": members}
    updated = await repo.update_deal(
        deal_id,
        {"facilitator_slots": slots, "participants": members, "status": _advance(patched)},
    )
    return _serialize(updated)


async def attach_document(deal_id: str, user: dict[str, Any], file_id: str) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_party(deal, user["_id"])
    _assert_not_terminal(deal)
    docs = _dedupe([*deal.get("documents", []), file_id])
    updated = await repo.update_deal(deal_id, {"documents": docs, "status": _advance(deal)})
    return _serialize(updated)


async def agree(deal_id: str, user: dict[str, Any]) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    _assert_not_terminal(deal)

    principals = list(deal.get("principals", []))
    for p in principals:
        if p["user_id"] == user["_id"]:
            p["agreed"] = True
    patched = {**deal, "principals": principals}
    updated = await repo.update_deal(deal_id, {"principals": principals, "status": _advance(patched)})
    return _serialize(updated)


async def cancel(deal_id: str, user: dict[str, Any]) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    if deal["status"] in TERMINAL_STATUSES:
        raise ConflictError(f"Deal is already {deal['status']}")
    updated = await repo.update_deal(deal_id, {"status": "cancelled"})
    return _serialize(updated)


async def handoff(deal_id: str, user: dict[str, Any]) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    if deal["status"] != "brief_ready":
        raise ConflictError("A Deal Brief must be assembled before handoff")
    updated = await repo.update_deal(deal_id, {"status": "handoff"})
    return _serialize(updated)


# ── Deal Brief (the deliverable) ─────────────────────────────────────────────
async def assemble_brief(deal_id: str, user: dict[str, Any], config: MarketplaceConfig) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    if deal["status"] not in ("agreed", "brief_ready"):
        raise ConflictError(
            "Deal must be 'agreed' (all principals agreed and facilitator slots resolved) "
            "before assembling a Deal Brief"
        )

    facts = _build_deal_facts(deal)
    citations, ref_block = await _retrieve_domain_context(facts, deal.get("vertical"))

    system_prompt = (
        "You are a neutral marketplace facilitator. Produce a Deal Brief — a structured handoff "
        "document that carries a deal into offline execution (for a bank, lawyer, broker, or "
        "logistics provider). Be factual; use only the information provided. Do not invent terms."
    )
    user_prompt = (
        f"{facts}\n\n"
        f"Relevant domain reference (use for context only, cite where used):\n{ref_block or '(none)'}\n\n"
        "Write the Deal Brief in Markdown with these sections: "
        "## Summary, ## Parties, ## Agreed Terms, ## Facilitators, ## Documents, "
        "## Domain Notes, ## Open Items."
    )

    try:
        from app.modules.ai.llm_client import generate

        markdown = await generate(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            use_case="deal_brief",
        )
    except Exception as exc:  # provider/config issues shouldn't 500 opaquely
        raise ServiceUnavailableError("Deal Brief generation unavailable: LLM call failed") from exc

    brief = {
        "markdown": markdown,
        "citations": citations,
        "use_case": "deal_brief",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    updated = await repo.update_deal(deal_id, {"brief": brief, "status": "brief_ready"})
    await _notify(_party_ids(deal), exclude=None, ntype="deal_brief_ready",
                  data={"deal_id": deal_id})
    return _serialize(updated)


async def get_brief(deal_id: str, user: dict[str, Any]) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_party(deal, user["_id"])
    brief = deal.get("brief")
    if not brief:
        raise NotFoundError("No Deal Brief has been assembled yet")
    return brief


# ── Helpers ──────────────────────────────────────────────────────────────────
def _principal(user_id: str, participant_type: str, config: MarketplaceConfig) -> dict[str, Any]:
    pt = config.get_type(participant_type)
    role = pt.role if pt else "supply"
    return {"user_id": user_id, "participant_type": participant_type, "role": role, "agreed": False}


def _facilitator_slots(config: MarketplaceConfig) -> list[dict[str, Any]]:
    return [
        {"role_type": pt.slug, "status": "needed", "user_id": None, "note": None}
        for pt in config.participant_types
        if pt.role == "facilitator"
    ]


def _vertical(config: MarketplaceConfig) -> str | None:
    ident = getattr(config, "marketplace", None)
    return getattr(ident, "vertical", None) or getattr(ident, "slug", None) or getattr(ident, "name", None)


def _advance(deal: dict[str, Any]) -> str:
    """Compute the next non-terminal status from the deal's contents."""
    if deal.get("status") in TERMINAL_STATUSES or deal.get("status") in ("brief_ready",):
        return deal["status"]
    principals = deal.get("principals", [])
    all_agreed = len(principals) >= 2 and all(p.get("agreed") for p in principals)
    slots_resolved = all(s.get("status") != "needed" for s in deal.get("facilitator_slots", []))
    return "agreed" if (all_agreed and slots_resolved) else "active"


def _build_deal_facts(deal: dict[str, Any]) -> str:
    lines = [f"# Deal facts", f"Vertical: {deal.get('vertical') or 'n/a'}"]
    lines.append("\n## Parties (principals)")
    for p in deal.get("principals", []):
        agreed = "agreed" if p.get("agreed") else "not yet agreed"
        lines.append(f"- {p.get('role', '?')}: {p.get('participant_type', '?')} "
                     f"(user {p.get('user_id')}) — {agreed}")
    lines.append("\n## Recorded terms")
    params = deal.get("parameters", [])
    if not params:
        lines.append("- (none recorded)")
    for t in params:
        unit = f" {t['unit']}" if t.get("unit") else ""
        flag = " [agreed]" if t.get("agreed") else ""
        label = t.get("label") or t.get("key")
        lines.append(f"- {label}: {t.get('value')}{unit}{flag}"
                     + (f" — {t['note']}" if t.get("note") else ""))
    lines.append("\n## Facilitators")
    slots = deal.get("facilitator_slots", [])
    if not slots:
        lines.append("- (none required)")
    for s in slots:
        who = f" (user {s['user_id']})" if s.get("user_id") else ""
        lines.append(f"- {s.get('role_type')}: {s.get('status')}{who}")
    docs = deal.get("documents", [])
    lines.append(f"\n## Documents\n- {len(docs)} attached document(s)")
    if deal.get("context"):
        lines.append(f"\n## Context\n{deal['context']}")
    return "\n".join(lines)


async def _retrieve_domain_context(facts: str, vertical: str | None) -> tuple[list[dict], str]:
    """Pull curated domain context from the reference library (wiki-preferred). Non-fatal."""
    try:
        from app.modules.ai.embedding_client import get_embedding
        from app.modules.knowledge import search_reference_library

        embedding = await get_embedding(facts[:4000])
        hits = await search_reference_library(embedding, top_k=5, vertical=vertical)
        citations = [
            {
                "id": h.get("id"),
                "score": round(float(h.get("score", 0)), 3),
                "source_layer": (h.get("metadata") or {}).get("source_layer"),
            }
            for h in hits
        ]
        ref_block = "\n\n".join(h["chunk_text"] for h in hits)
        return citations, ref_block
    except Exception:
        logger.warning("Deal Brief domain-context retrieval failed; continuing without it", exc_info=True)
        return [], ""


async def _notify(user_ids: list[str], *, exclude: str | None, ntype: str, data: dict) -> None:
    try:
        from app.modules.notifications.service import create_notification

        for uid in user_ids:
            if uid and uid != exclude:
                await create_notification(user_id=uid, notification_type=ntype, data=data)
    except Exception:
        logger.warning("Deal notification failed (non-fatal)", exc_info=True)


async def _get_or_404(deal_id: str) -> dict[str, Any]:
    deal = await repo.get_deal(deal_id)
    if not deal:
        raise NotFoundError("Deal not found")
    return deal


def _members_from_principals(principals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    members: list[dict[str, Any]] = []
    for p in principals:
        uid = p["user_id"]
        if uid not in seen:
            seen.add(uid)
            members.append({"user_id": uid, "role": p.get("role")})
    return members


def _party_ids(deal: dict[str, Any]) -> list[str]:
    return [m["user_id"] for m in deal.get("participants", [])]


def _assert_party(deal: dict[str, Any], user_id: str) -> None:
    if user_id not in _party_ids(deal):
        raise ForbiddenError("Not a party to this deal")


def _assert_principal(deal: dict[str, Any], user_id: str) -> None:
    if user_id not in [p["user_id"] for p in deal.get("principals", [])]:
        raise ForbiddenError("Only deal principals can perform this action")


def _assert_not_terminal(deal: dict[str, Any]) -> None:
    if deal.get("status") in TERMINAL_STATUSES:
        raise ConflictError(f"Deal is {deal['status']} and can no longer be modified")


def _dedupe(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for it in items:
        if it is not None:
            seen.setdefault(it, None)
    return list(seen.keys())


def _serialize(doc: dict[str, Any] | None) -> dict[str, Any]:
    if not doc:
        return {}
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
