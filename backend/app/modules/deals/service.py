"""Deals service — the confidential deal-assembly intermediary (GAP-4/5/6/15).

The deal is a **witnessed story-version chain**, not a mutable CRUD record. A match yields
an anonymous Stage-1 story version; parties respond with acknowledge / annotate / correct;
a version every required party has acknowledged (uncorrected, within the window) becomes a
**milestone**. Milestones accumulate detail until one validates as template-complete for the
chosen deal instrument and is acknowledged under the final wording — that milestone **is** the
Deal Brief. Two primitives only: ACKNOWLEDGE (epistemic) and CONSENT (authorization).

Design source: MarketForge `framework/story-progression-system.md`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.marketplace_config import MarketplaceConfig
from app.modules.deals import composer, repository as repo, story
from app.modules.deals.hashing import content_hash
from app.modules.deals.templates import validate_snapshot

logger = logging.getLogger("cosolvent.deals.service")

TERMINAL_DEAL_STATES = {"handoff", "closed", "cancelled"}


# ── small helpers ────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _window(config: MarketplaceConfig) -> timedelta:
    return timedelta(days=config.story_progression.acknowledgment_window_days)


def _disclosure_levels(config: MarketplaceConfig) -> list[str]:
    return list(config.story_progression.disclosure_levels)


def _final_level(config: MarketplaceConfig) -> str:
    return _disclosure_levels(config)[-1]


def _vertical(config: MarketplaceConfig) -> str | None:
    ident = getattr(config, "marketplace", None)
    return getattr(ident, "name", None)


def _serialize(doc: dict[str, Any] | None) -> dict[str, Any]:
    if not doc:
        return {}
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc


async def _get_or_404(deal_id: str) -> dict[str, Any]:
    deal = await repo.get_deal(deal_id)
    if not deal:
        raise NotFoundError("Deal not found")
    return deal


def _assert_party(deal: dict[str, Any], user_id: str) -> None:
    if not story.is_party(deal, user_id):
        raise ForbiddenError("Not a party to this deal")


def _assert_principal(deal: dict[str, Any], user_id: str) -> None:
    if story.party_role(deal, user_id) != "principal":
        raise ForbiddenError("Only deal principals can perform this action")


def _assert_not_terminal(deal: dict[str, Any]) -> None:
    if deal.get("status") in TERMINAL_DEAL_STATES:
        raise ConflictError(f"Deal is {deal['status']} and can no longer be modified")


def _instrument_required_fields(config: MarketplaceConfig, instrument: str | None) -> list[str]:
    inst = config.get_instrument(instrument) if instrument else None
    return list(inst.required_fields) if inst else []


# ── state recomputation (milestone status is always derived) ──────────────────
async def _recompute_versions(
    deal: dict[str, Any], config: MarketplaceConfig
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Recompute every version's derived state from responses; persist changed caches.

    Returns (versions, responses).
    """
    versions = await repo.list_versions(str(deal["_id"]))
    responses = await repo.list_responses_for_deal(str(deal["_id"]))
    window = _window(config)
    now = _now()
    for v in versions:
        if v.get("state") == story.SUPERSEDED:
            continue
        derived = story.compute_version_state(v, responses, now=now, window=window)
        if derived != v.get("state"):
            await repo.set_version_state(str(v["_id"]), derived)
            v["state"] = derived
    return versions, responses


def _current_version(versions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The live version = highest-seq non-superseded version."""
    live = [v for v in versions if v.get("state") != story.SUPERSEDED]
    return max(live, key=lambda v: v.get("seq", 0)) if live else None


def _latest_milestone(versions: list[dict[str, Any]]) -> dict[str, Any] | None:
    ms = [v for v in versions if v.get("state") == story.MILESTONE]
    return max(ms, key=lambda v: v.get("seq", 0)) if ms else None


def _next_seq(versions: list[dict[str, Any]]) -> int:
    return (max((v.get("seq", 0) for v in versions), default=0)) + 1


def _is_final_candidate(deal: dict[str, Any], version: dict[str, Any], config: MarketplaceConfig) -> bool:
    """A version can carry the final Deal-Brief acknowledgment iff it is at the final
    disclosure level, an instrument is chosen, and its snapshot is template-complete."""
    if version.get("disclosure_level") != _final_level(config):
        return False
    result = validate_snapshot(
        version.get("snapshot", {}), deal.get("instrument"), _instrument_required_fields(config, deal.get("instrument"))
    )
    return result.complete


def _ack_wording(deal: dict[str, Any], version: dict[str, Any], config: MarketplaceConfig) -> str:
    sp = config.story_progression
    return sp.final_signoff_wording if _is_final_candidate(deal, version, config) else sp.signoff_wording


# ── version composition ───────────────────────────────────────────────────────
async def _compose_and_publish(
    deal: dict[str, Any],
    config: MarketplaceConfig,
    *,
    versions: list[dict[str, Any]],
    text_inputs: list[str],
    composed_from: dict[str, Any],
) -> dict[str, Any]:
    """Compose the next immutable story version and publish it.

    The working snapshot is derived from the deal's responses (source of truth), then run
    through the Loop-3 consent gate: protected, unconsented attributes are redacted before
    publication (integrity rule 5). The narrative is composed from the *published* (redacted)
    snapshot only, with graded Tier-A/Tier-B evidence and the travel-test prompt.
    """
    deal_id = str(deal["_id"])
    disclosure = deal.get("disclosure_level", _disclosure_levels(config)[0])

    responses = await repo.list_responses_for_deal(deal_id)
    consents = await repo.list_consents_for_deal(deal_id)
    working = story.accumulate_snapshot(responses)
    owners = story.attribute_owners(responses)
    published, withheld = story.gate_snapshot(
        working, owners, consents, config.story_progression.protected_attributes, disclosure
    )

    # Tier-B (confirmed market conditions) — only past the anonymous stage, and never fatal.
    ref_block = ""
    if disclosure != _disclosure_levels(config)[0]:
        _, ref_block = await _retrieve_domain_context(" ".join(text_inputs) or disclosure, deal.get("vertical"))
    evidence = composer.grade_evidence(published, ref_block)

    narrative = composer.compose_narrative(deal, published, disclosure, text_inputs, evidence=evidence)
    narrative = await composer.enhance_narrative(narrative, disclosure)

    seq = _next_seq(versions)
    required = story.active_party_ids(deal)
    template_result = validate_snapshot(
        published, deal.get("instrument"), _instrument_required_fields(config, deal.get("instrument"))
    ).to_dict()

    version = {
        "deal_id": deal_id,
        "seq": seq,
        "disclosure_level": disclosure,
        "narrative": narrative,
        "snapshot": published,
        "content_hash": content_hash(disclosure, narrative, published),
        "required_acknowledgers": required,
        "composed_from": composed_from,
        "state": story.PUBLISHED,
        "published_at": _now().isoformat(),
        "template_result": template_result,
        "withheld": withheld,
        "is_final": False,
    }
    return await repo.create_version(version)


# ── creation ──────────────────────────────────────────────────────────────────
async def create_deal(user: dict[str, Any], body: Any, config: MarketplaceConfig) -> dict[str, Any]:
    parties: list[dict[str, Any]]

    if body.conversation_id:
        from app.modules.communication import repository as comms_repo

        conv = await comms_repo.get_conversation(body.conversation_id)
        if not conv:
            raise NotFoundError("Conversation not found")
        if user["_id"] not in [p["user_id"] for p in conv.get("participants", [])]:
            raise ForbiddenError("Not a participant in this conversation")
        conversation_id = str(conv["_id"])
        parties = [_principal_party(p["user_id"], p.get("participant_type", "")) for p in conv["participants"]]
    elif body.counterparty_user_id:
        from app.modules.auth.repository import find_user_by_id

        other = await find_user_by_id(body.counterparty_user_id)
        if not other:
            raise NotFoundError("Counterparty not found")
        conversation_id = None
        parties = [
            _principal_party(user["_id"], user.get("participant_type", "")),
            _principal_party(other["_id"], other.get("participant_type", "")),
        ]
    else:
        raise AppError("Provide either conversation_id or counterparty_user_id", 400)

    if len({p["user_id"] for p in parties}) < 2:
        raise AppError("A deal needs at least two distinct principals", 400)

    deal_doc = {
        "status": "active",
        "vertical": _vertical(config),
        "conversation_id": conversation_id,
        "instrument": None,
        "framework_scenario": getattr(body, "framework_scenario", None),
        "disclosure_level": _disclosure_levels(config)[0],
        "parties": parties,
        "participants": [{"user_id": p["user_id"], "role": p["role"]} for p in parties],
        "facilitator_slots": _facilitator_slots(config),
        "documents": [],
        "context": getattr(body, "context", None) or "",
        "created_by": user["_id"],
    }
    deal = await repo.create_deal(deal_doc)

    # A match exists → the platform composes the first (anonymous) story version.
    await _compose_and_publish(
        deal,
        config,
        versions=[],
        text_inputs=[deal_doc["context"]] if deal_doc["context"] else [],
        composed_from={"origin": "match"},
    )
    await _notify([p["user_id"] for p in parties], exclude=user["_id"], ntype="deal_created",
                  data={"deal_id": str(deal["_id"])})
    return await _deal_view(str(deal["_id"]), user, config)


def _principal_party(user_id: str, participant_type: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "participant_type": participant_type,
        "role": "principal",
        "joined_seq": 1,
        "exited_seq": None,
        "status": "active",
    }


def _facilitator_slots(config: MarketplaceConfig) -> list[dict[str, Any]]:
    return [
        {"role_type": pt.slug, "status": "needed", "user_id": None, "note": None}
        for pt in config.participant_types
        if pt.role == "facilitator"
    ]


# ── reads / views ──────────────────────────────────────────────────────────────
async def _deal_view(deal_id: str, user: dict[str, Any], config: MarketplaceConfig) -> dict[str, Any]:
    """Party-scoped view. Principals see the working chain; facilitators see only the
    current milestone (late joiners never read chain history — trajectory privacy, §7)."""
    deal = await _get_or_404(deal_id)
    _assert_party(deal, user["_id"])
    versions, responses = await _recompute_versions(deal, config)
    current = _current_version(versions)
    milestone = _latest_milestone(versions)
    role = story.party_role(deal, user["_id"])

    view = _serialize(deal)
    view["current_version"] = _version_view(deal, current, responses, config) if current else None
    view["current_milestone"] = _version_view(deal, milestone, responses, config) if milestone else None
    if role == "principal":
        view["versions"] = [_version_view(deal, v, responses, config) for v in versions]
    else:
        # facilitator: only the current milestone is visible, and only once audience consent cleared.
        party: dict[str, Any] = next((p for p in deal.get("parties", []) if p["user_id"] == user["_id"]), {})
        if party.get("status") != "active":
            view["current_milestone"] = None
            view["access"] = "pending_audience_consent"
        view["versions"] = []
    return view


def _version_view(
    deal: dict[str, Any], version: dict[str, Any] | None, responses: list[dict[str, Any]], config: MarketplaceConfig
) -> dict[str, Any] | None:
    if not version:
        return None
    v = _serialize(version)
    v["acknowledged_by"] = sorted(story.effective_acknowledgers(version, responses))
    v["pending_acknowledgers"] = story.pending_acknowledgers(version, responses)
    v["is_final_candidate"] = _is_final_candidate(deal, version, config)
    v["acknowledgment_wording"] = _ack_wording(deal, version, config)
    # Loop-3: attributes redacted from this published version pending owner consent.
    v["withheld"] = version.get("withheld", [])
    if not config.story_progression.pending_visibility:
        # pending-visibility is a social-pressure lever, off by default (§8).
        v.pop("pending_acknowledgers", None)
    return v


async def list_deals(user: dict[str, Any]) -> list[dict[str, Any]]:
    return [_serialize(d) for d in await repo.list_deals_for_user(user["_id"])]


async def get_deal(deal_id: str, user: dict[str, Any], config: MarketplaceConfig) -> dict[str, Any]:
    return await _deal_view(deal_id, user, config)


# ── respond: acknowledge / annotate / correct (§5) ──────────────────────────────
async def respond(deal_id: str, user: dict[str, Any], req: Any, config: MarketplaceConfig) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_party(deal, user["_id"])
    _assert_not_terminal(deal)

    party: dict[str, Any] = next((p for p in deal.get("parties", []) if p["user_id"] == user["_id"]), {})
    if party.get("status") != "active":
        raise ForbiddenError("You must be an active party (audience consent pending) to respond")

    versions, _ = await _recompute_versions(deal, config)
    current = _current_version(versions)
    if not current or current.get("state") not in (story.PUBLISHED, story.STALE, story.MILESTONE, story.BLOCKED):
        raise ConflictError("No open version to respond to")

    # Hash-pinning (integrity rule 2): a response must reference the exact content shown.
    if req.content_hash != current.get("content_hash"):
        raise ConflictError("Stale version: the story has changed; refetch before responding")

    if user["_id"] not in current.get("required_acknowledgers", []):
        raise ForbiddenError("You are not a required acknowledger of this version")

    param_updates: list[dict[str, Any]] = [
        p.model_dump() if hasattr(p, "model_dump") else dict(p) for p in getattr(req, "params", [])
    ]
    payload: dict[str, Any] = {"text": getattr(req, "text", None), "params": param_updates}
    await repo.create_response({
        "deal_id": str(deal["_id"]),
        "version_id": str(current["_id"]),
        "content_hash": current["content_hash"],
        "user_id": user["_id"],
        "type": req.type,
        "payload": payload,
    })

    if req.type == "correct":
        # A correction supersedes (never edits) via the shared update-and-recompose path.
        # Its params are already persisted on the response, so the recomposed working
        # snapshot (derived from responses) picks them up automatically.
        await repo.set_version_state(str(current["_id"]), story.SUPERSEDED)
        versions = await repo.list_versions(str(deal["_id"]))
        text_inputs = [f"Correction: {payload['text']}"] if payload["text"] else ["A correction was applied."]
        await _compose_and_publish(
            deal, config, versions=versions, text_inputs=text_inputs,
            composed_from={"supersedes": str(current["_id"]), "reason": "correction"},
        )
        await _notify(story.active_party_ids(deal), exclude=None, ntype="deal_version_superseded",
                      data={"deal_id": deal_id})
    else:
        # Recompute; if this response completes a milestone, react.
        versions, responses = await _recompute_versions(deal, config)
        refreshed = await repo.get_version(str(current["_id"]))
        if refreshed and refreshed.get("state") == story.MILESTONE:
            await _on_milestone_reached(deal, refreshed, config)

    return await _deal_view(deal_id, user, config)


async def _on_milestone_reached(deal: dict[str, Any], version: dict[str, Any], config: MarketplaceConfig) -> None:
    await _notify(story.active_party_ids(deal), exclude=None, ntype="deal_milestone",
                  data={"deal_id": str(deal["_id"]), "seq": version.get("seq")})
    # GAP-7 injection trigger: once the deal is in assembly (deal_context), search facilitators
    # for any still-needed role slot and attach candidates. Non-fatal.
    if deal.get("disclosure_level") == _final_level(config):
        try:
            await _autofill_facilitator_candidates(deal, config)
        except Exception:
            logger.info("facilitator autofill skipped", exc_info=True)
    # Final Deal Brief: a template-complete, final-level milestone acknowledged by all.
    if _is_final_candidate(deal, version, config):
        await _finalize_brief(deal, version, config)


# ── advance / continue: compose the next version from queued annotations ─────────
async def advance(deal_id: str, user: dict[str, Any], config: MarketplaceConfig) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    _assert_not_terminal(deal)

    versions, responses = await _recompute_versions(deal, config)
    milestone = _latest_milestone(versions)
    if not milestone:
        raise ConflictError("No milestone yet; the current version must be acknowledged first")
    current = _current_version(versions)
    if current and current.get("state") != story.MILESTONE:
        raise ConflictError("The current version is still open; nothing to advance from")

    # Queued annotations pinned to the milestone become narrative inputs (their params are
    # already in the responses, so the recomposed snapshot picks them up automatically).
    annos = [
        r for r in responses
        if r.get("version_id") == str(milestone["_id"]) and r.get("type") == "annotate"
    ]
    text_inputs = [a["payload"].get("text") for a in annos if a.get("payload", {}).get("text")]

    await _compose_and_publish(
        deal, config, versions=versions,
        text_inputs=text_inputs or ["Continuing from the last milestone."],
        composed_from={"from_milestone": str(milestone["_id"]), "annotations": [str(a["_id"]) for a in annos]},
    )
    return await _deal_view(deal_id, user, config)


# ── consent: disclosure advance / audience expansion (§4) ────────────────────────
async def consent(deal_id: str, user: dict[str, Any], req: Any, config: MarketplaceConfig) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_party(deal, user["_id"])
    _assert_not_terminal(deal)

    scope = req.scope
    if scope == "disclosure_advance":
        _assert_principal(deal, user["_id"])
        levels = _disclosure_levels(config)
        target = req.target or story.next_disclosure_level(deal.get("disclosure_level", levels[0]), levels)
        if not target:
            raise ConflictError("Already at the maximum disclosure level")
        versions, _ = await _recompute_versions(deal, config)
        if not _latest_milestone(versions):
            raise ConflictError("Disclosure can only advance after the first milestone is reached")

        await repo.create_consent({"deal_id": deal_id, "user_id": user["_id"], "scope": scope, "target": target})
        consents = await repo.list_consents_for_deal(deal_id)
        if story.all_principals_consented(deal, consents, scope=scope, target=target):
            deal = await repo.update_deal(deal_id, {"disclosure_level": target}) or deal
            await _compose_and_publish(
                deal, config, versions=versions,
                text_inputs=[f"Disclosure advanced to '{target}'."],
                composed_from={"disclosure_advance": target},
            )
            await _notify(story.active_party_ids(deal), exclude=None, ntype="deal_disclosure_advanced",
                          data={"deal_id": deal_id, "level": target})

    elif scope == "audience_expansion":
        _assert_principal(deal, user["_id"])
        target = req.target
        if not target:
            raise AppError("audience_expansion consent requires the joining party's user id as target", 400)
        await repo.create_consent({"deal_id": deal_id, "user_id": user["_id"], "scope": scope, "target": target})
        consents = await repo.list_consents_for_deal(deal_id)
        if story.all_principals_consented(deal, consents, scope=scope, target=target):
            parties = deal.get("parties", [])
            for p in parties:
                if p["user_id"] == target and p.get("status") == "pending_audience_consent":
                    p["status"] = "active"
            await repo.update_deal(deal_id, {"parties": parties})
            await _notify([target], exclude=None, ntype="deal_audience_granted", data={"deal_id": deal_id})

    else:  # attribute consent (Loop-3) — authorize disclosing one protected attribute
        if not req.target:
            raise AppError("attribute consent requires the attribute key as target", 400)
        # Scope the consent to the current disclosure level, so a wider future audience must
        # re-consent (the §4 per-audience rule). The owner authorizes only their own attribute.
        await repo.create_consent({
            "deal_id": deal_id, "user_id": user["_id"], "scope": scope,
            "target": req.target, "level": deal.get("disclosure_level"),
        })
        # Recompose: supersede the current version so the now-consented value can appear
        # (the gate re-runs; the value flows in from responses).
        versions, _ = await _recompute_versions(deal, config)
        current = _current_version(versions)
        if current and current.get("state") != story.SUPERSEDED:
            await repo.set_version_state(str(current["_id"]), story.SUPERSEDED)
            versions = await repo.list_versions(deal_id)
            await _compose_and_publish(
                deal, config, versions=versions,
                text_inputs=[f"Attribute '{req.target}' cleared for disclosure."],
                composed_from={"supersedes": str(current["_id"]), "reason": "attribute_consent", "attribute": req.target},
            )

    return await _deal_view(deal_id, user, config)


# ── instrument selection (unlocks template completeness) ─────────────────────────
async def set_instrument(deal_id: str, user: dict[str, Any], instrument: str, config: MarketplaceConfig) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    _assert_not_terminal(deal)
    if not config.get_instrument(instrument):
        valid = ", ".join(i.name for i in config.instruments())
        raise AppError(f"Unknown deal instrument '{instrument}'. Valid: {valid}", 400)
    await repo.update_deal(deal_id, {"instrument": instrument})
    return await _deal_view(deal_id, user, config)


# ── facilitator slots + injection (GAP-7) ────────────────────────────────────────
async def search_facilitators(
    deal: dict[str, Any], role_type: str, config: MarketplaceConfig, *, limit: int = 5
) -> list[dict[str, Any]]:
    """Deal → ranked facilitator candidates of ``role_type`` (semantic search over that
    facilitator type's profiles, keyed off the deal's current story). Non-fatal → []."""
    try:
        from app.modules.ai.embedding_client import get_embedding
        from app.modules.discovery import vector_service
    except Exception:
        return []
    versions = await repo.list_versions(str(deal["_id"]))
    ref = _latest_milestone(versions) or _current_version(versions) or {}
    text = ref.get("narrative") or deal.get("context") or role_type
    try:
        embedding = await get_embedding(str(text)[:4000])
        hits = await vector_service.search_profile_vectors_strict(
            embedding, participant_types=[role_type], limit=limit
        )
    except Exception:
        logger.info("facilitator search unavailable", exc_info=True)
        return []
    out: list[dict[str, Any]] = []
    for h in hits:
        prof = h.get("profile") or {}
        out.append({
            "profile_id": h.get("id"),
            "user_id": prof.get("user_id"),
            "score": round(float(h.get("score", 0)), 3),
            "fields": prof.get("fields") or {},
        })
    return out


async def _autofill_facilitator_candidates(deal: dict[str, Any], config: MarketplaceConfig) -> None:
    """Search candidates for each still-needed facilitator slot and attach them (trigger)."""
    slots = list(deal.get("facilitator_slots", []))
    changed = False
    for slot in slots:
        if slot.get("status") == "needed" and not slot.get("candidates"):
            cands = await search_facilitators(deal, slot["role_type"], config, limit=5)
            if cands:
                slot["candidates"] = cands
                slot["status"] = "searching"
                changed = True
    if changed:
        await repo.update_deal(str(deal["_id"]), {"facilitator_slots": slots})


async def facilitator_candidates(
    deal_id: str, user: dict[str, Any], role_type: str, config: MarketplaceConfig
) -> dict[str, Any]:
    """On-demand facilitator search for a role slot (principal-only)."""
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    return {"role_type": role_type, "candidates": await search_facilitators(deal, role_type, config)}


async def set_facilitator(deal_id: str, user: dict[str, Any], req: Any, config: MarketplaceConfig) -> dict[str, Any]:
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

    parties = list(deal.get("parties", []))
    participants = list(deal.get("participants", []))
    if req.status == "confirmed" and req.user_id and not story.is_party(deal, req.user_id):
        # Injection = a party-set edit. The joiner starts PENDING audience-expansion consent;
        # they read nothing until every principal consents (§7).
        versions = await repo.list_versions(deal_id)
        parties.append({
            "user_id": req.user_id,
            "participant_type": req.role_type,
            "role": "facilitator",
            "joined_seq": _next_seq(versions),
            "exited_seq": None,
            "status": "pending_audience_consent",
        })
        participants.append({"user_id": req.user_id, "role": "facilitator"})

    await repo.update_deal(deal_id, {"facilitator_slots": slots, "parties": parties, "participants": participants})
    if req.status == "confirmed" and req.user_id:
        await _notify(story.principal_ids(deal), exclude=None, ntype="deal_facilitator_pending",
                      data={"deal_id": deal_id, "facilitator": req.user_id})
    return await _deal_view(deal_id, user, config)


# ── reopen / revive / handoff / cancel ───────────────────────────────────────────
async def reopen(deal_id: str, user: dict[str, Any], matter: str | None, config: MarketplaceConfig) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    _assert_not_terminal(deal)
    versions, _ = await _recompute_versions(deal, config)
    milestone = _latest_milestone(versions)
    if not milestone:
        raise ConflictError("Nothing to reopen: no milestone exists")
    await _compose_and_publish(
        deal, config, versions=versions,
        text_inputs=[f"Reopened: {matter}" if matter else "A settled matter was reopened."],
        composed_from={"reopen_of": str(milestone["_id"]), "matter": matter},
    )
    if deal.get("status") == "brief_ready":
        await repo.update_deal(deal_id, {"status": "active"})
    return await _deal_view(deal_id, user, config)


async def revive_version(deal_id: str, version_id: str, user: dict[str, Any], config: MarketplaceConfig) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_party(deal, user["_id"])
    _assert_not_terminal(deal)
    version = await repo.get_version(version_id)
    if not version or version.get("deal_id") != deal_id:
        raise NotFoundError("Version not found")
    # No timeout ever closes a deal (rule 8): a stale version is always revivable.
    await repo.set_version_state(version_id, story.PUBLISHED, {"published_at": _now().isoformat()})
    responses = await repo.list_responses_for_deal(deal_id)
    await _notify(story.pending_acknowledgers(version, responses), exclude=None,
                  ntype="deal_version_revived", data={"deal_id": deal_id, "version_id": version_id})
    return await _deal_view(deal_id, user, config)


async def handoff(deal_id: str, user: dict[str, Any], config: MarketplaceConfig) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    if deal.get("status") != "brief_ready":
        raise ConflictError("The final Deal Brief must be reached before handoff")
    await repo.update_deal(deal_id, {"status": "handoff"})
    return await _deal_view(deal_id, user, config)


async def cancel(deal_id: str, user: dict[str, Any], config: MarketplaceConfig) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_principal(deal, user["_id"])
    if deal.get("status") in TERMINAL_DEAL_STATES:
        raise ConflictError(f"Deal is already {deal['status']}")
    await repo.update_deal(deal_id, {"status": "cancelled"})
    return await _deal_view(deal_id, user, config)


# ── final Deal Brief render (GAP-5) ──────────────────────────────────────────────
async def _finalize_brief(deal: dict[str, Any], version: dict[str, Any], config: MarketplaceConfig) -> None:
    versions = await repo.list_versions(str(deal["_id"]))
    responses = await repo.list_responses_for_deal(str(deal["_id"]))
    provenance = [
        {
            "seq": v.get("seq"),
            "disclosure_level": v.get("disclosure_level"),
            "acknowledged_by": sorted(story.effective_acknowledgers(v, responses)),
        }
        for v in versions
        if v.get("state") == story.MILESTONE
    ]
    citations, ref_block = await _retrieve_domain_context(version.get("narrative", ""), deal.get("vertical"))
    markdown = composer.render_brief_markdown(deal, version, ref_block, provenance)
    brief = {"markdown": markdown, "citations": citations, "generated_at": _now().isoformat()}
    await repo.set_version_state(str(version["_id"]), story.MILESTONE, {"is_final": True, "brief": brief})
    await repo.update_deal(str(deal["_id"]), {"status": "brief_ready"})
    await _notify(story.active_party_ids(deal), exclude=None, ntype="deal_brief_ready",
                  data={"deal_id": str(deal["_id"])})


async def get_brief(deal_id: str, user: dict[str, Any], config: MarketplaceConfig) -> dict[str, Any]:
    deal = await _get_or_404(deal_id)
    _assert_party(deal, user["_id"])
    versions = await repo.list_versions(deal_id)
    final = next((v for v in versions if v.get("is_final")), None)
    if not final or not final.get("brief"):
        raise NotFoundError("No final Deal Brief has been reached yet")
    return final["brief"]


# ── infra ────────────────────────────────────────────────────────────────────────
async def _retrieve_domain_context(text: str, vertical: str | None) -> tuple[list[dict], str]:
    """Pull curated domain context (rate benchmarks, escape hatches) from the reference
    library for the value-drivers section. Non-fatal."""
    try:
        from app.modules.ai.embedding_client import get_embedding
        from app.modules.knowledge import search_reference_library

        embedding = await get_embedding((text or "")[:4000])
        hits = await search_reference_library(embedding, top_k=5, vertical=vertical)
        citations = [
            {"id": h.get("id"), "score": round(float(h.get("score", 0)), 3),
             "source_layer": (h.get("metadata") or {}).get("source_layer")}
            for h in hits
        ]
        ref_block = "\n\n".join(h["chunk_text"] for h in hits)
        return citations, ref_block
    except Exception:
        logger.info("Deal Brief domain-context retrieval unavailable; continuing without it", exc_info=True)
        return [], ""


async def _notify(user_ids: list[str], *, exclude: str | None, ntype: str, data: dict) -> None:
    try:
        from app.modules.notifications.service import create_notification

        for uid in dict.fromkeys(user_ids):  # de-dupe, preserve order
            if uid and uid != exclude:
                await create_notification(user_id=uid, notification_type=ntype, data=data)
    except Exception:
        logger.warning("Deal notification failed (non-fatal)", exc_info=True)
