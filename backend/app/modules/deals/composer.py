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


def compose_narrative(
    deal: dict[str, Any],
    snapshot: dict[str, Any],
    disclosure_level: str,
    inputs: list[str],
) -> str:
    """Deterministic Content-Match-Story draft for the current disclosure level.

    ``inputs`` are free-text carry-overs (annotations, corrections) folded into the draft.
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
    if inputs:
        lines.append("**Incorporated in this version:**")
        lines.extend(f"- {i}" for i in inputs if i)
    return "\n".join(lines).strip()


async def enhance_narrative(base_narrative: str, disclosure_level: str) -> str:
    """Optionally polish the deterministic draft with the LLM. Never fatal.

    Respects the disclosure level in the instruction so the model does not invent
    identities at the anonymous stage.
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
                        "You are a neutral marketplace facilitator composing a short, self-contained "
                        "'Content Match Story' — an account of where a deal currently stands that must "
                        "read well when forwarded to someone with no prior context. Be factual; use only "
                        f"the information provided. {guard}"
                    ),
                },
                {"role": "user", "content": f"Rewrite this into a tight narrative, preserving all facts:\n\n{base_narrative}"},
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
