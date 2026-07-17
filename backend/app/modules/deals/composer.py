"""Composition of story versions and rendering of the final Deal Brief.

The composer turns the deal's current snapshot + queued inputs into the next narrative.
It is disclosure-aware (GAP-6): at ``anonymous`` level it describes *capability, not
identity*; identities only appear once the deal has advanced to ``named``.

Composition has a deterministic core (so the engine works with no LLM and is testable)
and an optional LLM enhancement that is used when available and skipped on any failure.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("cosolvent.deals.composer")


def _party_descriptor(party: dict[str, Any], disclosure_level: str) -> str:
    """How a party is referred to at a given disclosure level."""
    role = party.get("role", "party")
    ptype = party.get("participant_type") or role
    if disclosure_level == "anonymous":
        # Capability, not identity (GAP-6 anonymous-presentation rule).
        return f"a {ptype.replace('_', ' ')}"
    name = party.get("display_name") or party.get("participant_type") or party.get("user_id")
    return f"{name} ({ptype.replace('_', ' ')})"


def _snapshot_lines(snapshot: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, entry in (snapshot or {}).items():
        if isinstance(entry, dict):
            label = entry.get("label") or key
            value = entry.get("value")
            unit = f" {entry['unit']}" if entry.get("unit") else ""
        else:
            label, value, unit = key, entry, ""
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        lines.append(f"- **{label}:** {value}{unit}")
    return lines


def grade_evidence(snapshot: dict[str, Any], market_context: str = "") -> dict[str, Any]:
    """Grade composition inputs by evidence tier (§8 / evidence-relevance-tiers).

    * Tier A — deal-specific facts (the party-agreed snapshot). Anchors the case.
    * Tier B — confirmed market conditions (curated reference-library context).
    * Tier C — speculative signals. Deliberately EXCLUDED from version content.

    Withheld (redacted) snapshot entries are not evidence — they carry no value yet.
    """
    tier_a = [
        f"{(v.get('label') or k) if isinstance(v, dict) else k}: "
        f"{v.get('value') if isinstance(v, dict) else v}"
        f"{(' ' + v['unit']) if isinstance(v, dict) and v.get('unit') else ''}"
        for k, v in (snapshot or {}).items()
        if not (isinstance(v, dict) and (v.get("withheld") or v.get("value") in (None, "")))
    ]
    return {"tier_a": tier_a, "tier_b": (market_context or "").strip(), "tier_c_excluded": True}


def compose_narrative(
    deal: dict[str, Any],
    snapshot: dict[str, Any],
    disclosure_level: str,
    inputs: list[str],
    *,
    evidence: dict[str, Any] | None = None,
) -> str:
    """Deterministic Content-Match-Story draft for the current disclosure level.

    ``inputs`` are free-text carry-overs (annotations, corrections). ``evidence`` (if given)
    supplies graded Tier-A/Tier-B material for the value/skeptic sections; Tier C never enters.
    """
    parties = [p for p in deal.get("parties", []) if p.get("status") == "active"]
    who = "; ".join(_party_descriptor(p, disclosure_level) for p in parties) or "the parties"

    if disclosure_level == "anonymous":
        header = "A potential match has been identified."
    elif disclosure_level == "named":
        header = "The parties have revealed their identities and are exploring a deal."
    else:
        header = "The parties are assembling the deal."

    lines = [header, "", f"**Parties:** {who}.", ""]
    snap_lines = _snapshot_lines(snapshot)
    if snap_lines:
        lines.append("**Where things stand:**")
        lines.extend(snap_lines)
        lines.append("")
    ev = evidence or {}
    if ev.get("tier_b"):
        # Skeptic-addressed / evidence-weighted: ground the case in confirmed market context.
        lines.append("**Why this holds up (market context):**")
        lines.append(ev["tier_b"][:600])
        lines.append("")
    if inputs:
        lines.append("**Incorporated in this version:**")
        lines.extend(f"- {i}" for i in inputs if i)
    return "\n".join(lines).strip()


# The four travel properties (§8) the composer's prompt must satisfy. Forwarding-safety is
# additionally enforced mechanically by the consent engine (redaction) before publication.
_TRAVEL_TEST = (
    "The account must pass the 'travel test' — it will be forwarded to an approver who was "
    "never briefed:\n"
    "1) SELF-CONTAINED: legible cold, no prior context assumed.\n"
    "2) SKEPTIC-ADDRESSED: surface and answer the single most likely objection.\n"
    "3) EVIDENCE-WEIGHTED: rest claims on the provided deal facts (Tier A) and market context "
    "(Tier B) only; NEVER introduce speculation, predictions, or unstated signals (Tier C).\n"
    "4) FORWARDING-SAFE: reveal nothing beyond what is present; invent no facts."
)


async def enhance_narrative(base_narrative: str, disclosure_level: str) -> str:
    """Optionally polish the deterministic draft with the LLM, enforcing the travel test.
    Never fatal — falls back to the deterministic draft.
    """
    try:
        from app.modules.ai.llm_client import generate

        guard = (
            "Do NOT invent or infer participant identities, company names, or locations; "
            "describe capability only."
            if disclosure_level == "anonymous"
            else "You may use the identities already present; do not invent new facts."
        )
        out = await generate(
            [
                {
                    "role": "system",
                    "content": (
                        "You are a neutral marketplace facilitator composing a short 'Content Match "
                        "Story' — an account of where a deal currently stands. Use only the information "
                        f"provided. {guard}\n\n{_TRAVEL_TEST}"
                    ),
                },
                {"role": "user", "content": f"Rewrite this into a tight, travel-safe narrative, preserving all facts:\n\n{base_narrative}"},
            ],
            use_case="match_story",
        )
        return out.strip() or base_narrative
    except Exception:
        logger.info("Story narrative LLM enhancement unavailable; using deterministic draft", exc_info=True)
        return base_narrative


def render_brief_markdown(
    deal: dict[str, Any],
    version: dict[str, Any],
    ref_block: str,
    provenance: list[dict[str, Any]],
) -> str:
    """Render the final milestone as the Deal Brief document (GAP-5).

    Includes a value-drivers section surfacing knowledge-pack content and a provenance
    header derived from the milestone chain (which comes free — the chain IS the provenance).
    """
    disclosure = version.get("disclosure_level", "deal_context")
    parties = [p for p in deal.get("parties", []) if p.get("status") == "active"]
    who = "\n".join(f"- {_party_descriptor(p, disclosure)} — role: {p.get('role')}" for p in parties)

    lines = [
        "# Deal Brief",
        "",
        "> This is a non-binding summary for the parties' own use, not a contract.",
        "",
        "## Summary",
        version.get("narrative", ""),
        "",
        "## Parties",
        who or "- (none)",
        "",
        "## Agreed Terms",
    ]
    snap_lines = _snapshot_lines(version.get("snapshot", {}))
    lines.extend(snap_lines or ["- (none recorded)"])
    lines += ["", "## Instrument", f"- {deal.get('instrument') or 'unspecified'}"]

    slots = deal.get("facilitator_slots", [])
    lines += ["", "## Facilitators"]
    lines += [f"- {s.get('role_type')}: {s.get('status')}" for s in slots] or ["- (none required)"]

    if ref_block:
        lines += ["", "## Value Drivers (from the reference library)", ref_block]

    lines += ["", "## Provenance"]
    if provenance:
        for m in provenance:
            lines.append(
                f"- Milestone v{m.get('seq')} ({m.get('disclosure_level')}): "
                f"acknowledged by {', '.join(m.get('acknowledged_by', [])) or 'n/a'}"
            )
    lines.append(f"- Framework scenario: {deal.get('framework_scenario') or 'unspecified'}")
    return "\n".join(lines).strip()
