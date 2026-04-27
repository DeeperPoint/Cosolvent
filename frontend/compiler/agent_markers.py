"""Helpers for AGENT_FILL marker parsing and safe replacement."""

from __future__ import annotations

from dataclasses import dataclass
import re

# Match full JSX comments so replacement spans exclude the ``*/}`` / ``{/*`` delimiters.
# (Matching only ``AGENT_FILL:id:start`` would slice out those delimiters and corrupt the file.)
_START_RE = re.compile(r"\{/\*\s*AGENT_FILL:([a-zA-Z0-9_-]+):start\s*\*/\}")
_END_RE = re.compile(r"\{/\*\s*AGENT_FILL:([a-zA-Z0-9_-]+):end\s*\*/\}")


@dataclass(frozen=True)
class FillMarker:
    marker_id: str
    start_token_start: int
    start_token_end: int
    end_token_start: int
    end_token_end: int


class MarkerValidationError(ValueError):
    """Raised when AGENT_FILL markers are malformed."""


def find_fill_markers(content: str) -> list[FillMarker]:
    """Return validated markers sorted by position."""
    starts = [(m.group(1), m.start(), m.end()) for m in _START_RE.finditer(content)]
    ends = [(m.group(1), m.start(), m.end()) for m in _END_RE.finditer(content)]

    if not starts and not ends:
        return []
    if len(starts) != len(ends):
        raise MarkerValidationError(
            f"Mismatched marker count: {len(starts)} starts vs {len(ends)} ends"
        )

    markers: list[FillMarker] = []
    cursor = 0
    used_ids: set[str] = set()
    for sid, s0, s1 in starts:
        end_tuple = None
        for eid, e0, e1 in ends:
            if eid == sid and e0 > s1 and e0 >= cursor:
                end_tuple = (eid, e0, e1)
                break
        if end_tuple is None:
            raise MarkerValidationError(f"No end marker found for '{sid}'")
        if sid in used_ids:
            raise MarkerValidationError(f"Duplicate marker id '{sid}' is not allowed")
        used_ids.add(sid)
        _, e0, e1 = end_tuple
        markers.append(
            FillMarker(
                marker_id=sid,
                start_token_start=s0,
                start_token_end=s1,
                end_token_start=e0,
                end_token_end=e1,
            )
        )
        cursor = e1

    markers.sort(key=lambda m: m.start_token_start)
    return markers


def apply_marker_replacements(content: str, replacements: dict[str, str]) -> str:
    """Replace marker body content safely, preserving marker tokens."""
    markers = find_fill_markers(content)
    if not markers:
        return content

    missing = [k for k in replacements if k not in {m.marker_id for m in markers}]
    if missing:
        raise MarkerValidationError(f"Unknown marker ids in replacements: {', '.join(missing)}")

    updated = content
    for marker in reversed(markers):
        if marker.marker_id not in replacements:
            continue
        replacement = replacements[marker.marker_id]
        start_ix = marker.start_token_end
        end_ix = marker.end_token_start
        updated = updated[:start_ix] + "\n" + replacement.rstrip() + "\n" + updated[end_ix:]
    return updated
