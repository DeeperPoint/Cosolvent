"""Pure logic for the Story Progression System (GAP-4).

Everything here is side-effect free and DB-free so it can be unit-tested in isolation.
The service layer (``service.py``) wires these functions to persistence and the LLM.

Integrity rules enforced here (story-progression-system §11):
  1. Versions are immutable; a correction supersedes, never edits.
  2. Acknowledgments are version-hash-pinned.
  3. Milestone status is DERIVED from responses — never a stored flag.
  8. No timeout ever closes a deal; staleness is always revivable while the deal is open.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

# The two response kinds that count toward a milestone. `correct` blocks it.
ACK_TYPES = {"acknowledge", "annotate"}

# Version lifecycle states (story-progression-system §6).
DRAFT = "draft"
PUBLISHED = "published"
MILESTONE = "milestone"
BLOCKED = "blocked"
STALE = "stale"
SUPERSEDED = "superseded"


def _as_dt(value: Any) -> datetime | None:
    """Accept a datetime or an ISO-8601 string (docs round-trip timestamps as strings)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def pinned_responses(version: dict[str, Any], responses: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Responses that pin to THIS version's current content hash (rule 2).

    A response carrying a stale hash (the content moved on) is ignored — this is what
    makes acknowledgments non-transferable across content changes.
    """
    h = version.get("content_hash")
    return [r for r in responses if r.get("content_hash") == h]


def effective_acknowledgers(version: dict[str, Any], responses: Iterable[dict[str, Any]]) -> set[str]:
    """User ids whose acknowledge/annotate pins to this version's hash."""
    return {
        r["user_id"]
        for r in pinned_responses(version, responses)
        if r.get("type") in ACK_TYPES and r.get("user_id")
    }


def has_unresolved_correction(version: dict[str, Any], responses: Iterable[dict[str, Any]]) -> bool:
    """True if any `correct` pins to this version's hash."""
    return any(r.get("type") == "correct" for r in pinned_responses(version, responses))


def compute_version_state(
    version: dict[str, Any],
    responses: Iterable[dict[str, Any]],
    *,
    now: datetime,
    window: timedelta,
) -> str:
    """Derive a published version's lifecycle state from its responses (rule 3).

    Precedence: a version already superseded/draft stays as-is; a correction blocks;
    a full uncorrected acknowledger set within the window is a milestone; otherwise the
    version is stale past the window (dormant, revivable) or still published.
    """
    state = version.get("state")
    if state in (SUPERSEDED, DRAFT):
        return state

    responses = list(responses)
    if has_unresolved_correction(version, responses):
        return BLOCKED

    required = set(version.get("required_acknowledgers", []))
    ackers = effective_acknowledgers(version, responses)
    if required and required.issubset(ackers):
        return MILESTONE

    published_at = _as_dt(version.get("published_at"))
    if published_at is not None and now - published_at > window:
        return STALE
    return PUBLISHED


def pending_acknowledgers(version: dict[str, Any], responses: Iterable[dict[str, Any]]) -> list[str]:
    """Required acknowledgers who have not yet acknowledged this version's current hash."""
    required = list(version.get("required_acknowledgers", []))
    ackers = effective_acknowledgers(version, responses)
    return [uid for uid in required if uid not in ackers]


# ── party helpers ──────────────────────────────────────────────────────────

def active_parties(deal: dict[str, Any], *, role: str | None = None) -> list[dict[str, Any]]:
    out = []
    for p in deal.get("parties", []):
        if p.get("status") != "active":
            continue
        if p.get("exited_seq") is not None:
            continue
        if role is not None and p.get("role") != role:
            continue
        out.append(p)
    return out


def active_party_ids(deal: dict[str, Any], *, role: str | None = None) -> list[str]:
    return [p["user_id"] for p in active_parties(deal, role=role)]


def principal_ids(deal: dict[str, Any]) -> list[str]:
    return active_party_ids(deal, role="principal")


def is_party(deal: dict[str, Any], user_id: str) -> bool:
    return any(p.get("user_id") == user_id for p in deal.get("parties", []))


def party_role(deal: dict[str, Any], user_id: str) -> str | None:
    for p in deal.get("parties", []):
        if p.get("user_id") == user_id:
            return p.get("role")
    return None


# ── snapshot composition ─────────────────────────────────────────────────────

def merge_snapshot(base: dict[str, Any], updates: list[dict[str, Any]]) -> dict[str, Any]:
    """Fold structured parameter contributions into a snapshot.

    Each update is ``{"key","label","value","unit"}``. Later updates win. The result is a
    fresh dict (base is never mutated — versions are immutable).
    """
    merged: dict[str, Any] = {k: dict(v) if isinstance(v, dict) else v for k, v in (base or {}).items()}
    for upd in updates or []:
        key = upd.get("key")
        if not key:
            continue
        entry = merged.get(key, {}) if isinstance(merged.get(key), dict) else {}
        if upd.get("label") is not None:
            entry["label"] = upd["label"]
        if upd.get("value") is not None:
            entry["value"] = upd["value"]
        if upd.get("unit") is not None:
            entry["unit"] = upd["unit"]
        entry.setdefault("label", key)
        merged[key] = entry
    return merged


# ── disclosure levels ────────────────────────────────────────────────────────

def next_disclosure_level(current: str, levels: list[str]) -> str | None:
    """The stage after ``current`` in the configured disclosure ladder, or None at the top."""
    try:
        idx = levels.index(current)
    except ValueError:
        return None
    return levels[idx + 1] if idx + 1 < len(levels) else None


def all_principals_consented(
    deal: dict[str, Any],
    consents: Iterable[dict[str, Any]],
    *,
    scope: str,
    target: str,
) -> bool:
    """Every active principal has a consent record for (scope, target)."""
    principals = set(principal_ids(deal))
    if not principals:
        return False
    consented = {
        c["user_id"]
        for c in consents
        if c.get("scope") == scope and c.get("target") == target and c.get("user_id")
    }
    return principals.issubset(consented)


# ── snapshot accumulation (event-sourced from responses) ─────────────────────

def accumulate_snapshot(responses: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Fold every annotate/correct param contribution into the current working snapshot.

    Responses are the source of truth (§11): the snapshot is derived from them in
    chronological order, latest value winning per key. This is what lets a redacted value
    survive — it lives in the responses and is re-gated on each composition, not lost.
    """
    ordered = sorted(responses, key=lambda r: _as_dt(r.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc))
    snapshot: dict[str, Any] = {}
    for r in ordered:
        if r.get("type") not in ("annotate", "correct"):
            continue
        params = (r.get("payload") or {}).get("params") or []
        snapshot = merge_snapshot(snapshot, params)
    return snapshot


def attribute_owners(responses: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Map each contributed param key → the user id of its most recent contributor.

    The owner is who must consent before the attribute may be disclosed (Loop-3)."""
    ordered = sorted(responses, key=lambda r: _as_dt(r.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc))
    owners: dict[str, str] = {}
    for r in ordered:
        if r.get("type") not in ("annotate", "correct"):
            continue
        uid = r.get("user_id")
        for p in (r.get("payload") or {}).get("params") or []:
            if p.get("key") and uid:
                owners[p["key"]] = uid
    return owners


# ── Loop-3 consent engine: protected-attribute redaction (integrity rule 5) ──

def is_protected_key(key: str, protected: Iterable[str]) -> bool:
    kl = key.lower()
    return any(tok.lower() in kl for tok in protected)


def attribute_consented(
    key: str, owner: str | None, consents: Iterable[dict[str, Any]], level: str
) -> bool:
    """True if the attribute's owner has authorized disclosing ``key`` at ``level``.

    Consent is scoped to the disclosure level at which it was granted, so a wider audience
    (a higher level, or a joined facilitator) requires fresh consent — the §7/§4 re-consent
    rule. A consent recorded with level ``all`` covers every level.
    """
    if not owner:
        return False
    for c in consents:
        if (
            c.get("scope") == "attribute"
            and c.get("target") == key
            and c.get("user_id") == owner
            and c.get("level") in (None, "all", level)
        ):
            return True
    return False


def gate_snapshot(
    snapshot: dict[str, Any],
    owners: dict[str, str],
    consents: Iterable[dict[str, Any]],
    protected: Iterable[str],
    level: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Redact protected, unconsented attributes before publication (one canonical content).

    Returns ``(published_snapshot, withheld)``. A withheld entry keeps its key/label so the
    structure is legible, but the value is nulled and flagged — so a required protected field
    also keeps the version template-incomplete until its owner consents (you cannot finalize
    while withholding a required term).
    """
    consents = list(consents)
    published: dict[str, Any] = {}
    withheld: list[dict[str, Any]] = []
    for key, entry in (snapshot or {}).items():
        if is_protected_key(key, protected):
            owner = owners.get(key)
            if not attribute_consented(key, owner, consents, level):
                label = entry.get("label", key) if isinstance(entry, dict) else key
                published[key] = {"label": label, "value": None, "withheld": True}
                withheld.append({"key": key, "label": label, "owner": owner})
                continue
        published[key] = entry
    return published, withheld
