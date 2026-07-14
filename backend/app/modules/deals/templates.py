"""Template-completeness validator (GAP-5 / story-progression §9).

"Sufficient" is mechanical, not a judgment call: a version's structured snapshot is
complete for a deal instrument iff every field the instrument's template requires is
present with a non-empty value. This is the *guard* that unlocks the final acknowledgment;
until it passes, the UI can show exactly what is still missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompletenessResult:
    instrument: str | None
    complete: bool
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"instrument": self.instrument, "complete": self.complete, "missing": list(self.missing)}


def _has_value(entry: Any) -> bool:
    """A snapshot entry counts as present when it carries a non-empty value.

    Snapshot entries are ``{"label", "value", "unit"}`` dicts, but we tolerate bare
    scalars too so the validator is robust to composer variations.
    """
    if entry is None:
        return False
    value = entry.get("value") if isinstance(entry, dict) else entry
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def validate_snapshot(
    snapshot: dict[str, Any],
    instrument_name: str | None,
    required_fields: list[str],
) -> CompletenessResult:
    """Report whether ``snapshot`` satisfies ``required_fields`` for the instrument.

    With no instrument chosen yet the version can never be template-complete — a deal
    must declare its instrument before it can be finalized.
    """
    if instrument_name is None:
        return CompletenessResult(instrument=None, complete=False, missing=list(required_fields))

    present = {key for key, entry in (snapshot or {}).items() if _has_value(entry)}
    missing = [f for f in required_fields if f not in present]
    return CompletenessResult(instrument=instrument_name, complete=not missing, missing=missing)
