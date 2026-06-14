"""Validate-repair loop: the generator's acceptance oracle.

Imports Cosolvent's real ``MarketplaceConfig`` and runs the draft config dict through
it (including the ``cross_validate`` pass). Deterministic repairs are applied first;
anything left over is returned as structured errors for an optional LLM repair pass or
the human-review gate. We never emit a config that does not validate.
"""

from __future__ import annotations

from typing import Any, Callable

from pydantic import ValidationError

from app.core.marketplace_config import MarketplaceConfig


class ConfigValidationError(Exception):
    def __init__(self, errors: list[dict], draft: dict[str, Any]):
        self.errors = errors
        self.draft = draft
        super().__init__(f"Config did not validate after repairs: {len(errors)} error(s)")


def try_validate(draft: dict[str, Any]) -> tuple[MarketplaceConfig | None, list[dict]]:
    """Return (config, []) on success or (None, errors) on failure."""
    try:
        return MarketplaceConfig(**draft), []
    except ValidationError as e:
        return None, list(e.errors())


def _deterministic_repairs(draft: dict[str, Any], errors: list[dict]) -> bool:
    """Fix the mechanically-fixable validation failures in place. Returns True if it
    changed anything (worth re-validating)."""
    changed = False
    discovery = draft.setdefault("discovery", {})
    slugs = [p.get("slug") for p in draft.get("participant_types", [])]

    # All field names available across schemas (for filter_fields pruning).
    all_field_names: set[str] = set()
    searchable_names: set[str] = set()
    for schema in draft.get("profile_schemas", {}).values():
        for sec in schema.get("sections", []):
            for f in sec.get("fields", []):
                all_field_names.add(f.get("name"))
                if f.get("searchable"):
                    searchable_names.add(f.get("name"))

    # filter_fields must each exist in some profile schema -> drop unknowns.
    ff = [f for f in discovery.get("filter_fields", []) if f in all_field_names]
    if ff != discovery.get("filter_fields"):
        discovery["filter_fields"] = ff
        changed = True

    # searchable_types must reference visible-in-search types only.
    visible = {
        p["slug"] for p in draft.get("participant_types", [])
        if p.get("permissions", {}).get("visible_in_search")
    }
    st = [s for s in discovery.get("searchable_types", []) if s in visible and s in slugs]
    if not st and visible:
        st = sorted(visible)
    if st != discovery.get("searchable_types"):
        discovery["searchable_types"] = st
        changed = True

    return changed


def validate_and_repair(
    draft: dict[str, Any],
    *,
    llm_repair: Callable[[dict[str, Any], list[dict]], dict[str, Any]] | None = None,
    max_rounds: int = 5,
) -> MarketplaceConfig:
    """Drive the draft to a valid MarketplaceConfig or raise ConfigValidationError.

    Order per round: validate -> deterministic repairs -> (optional) LLM repair.
    """
    last_errors: list[dict] = []
    for _ in range(max_rounds):
        cfg, errors = try_validate(draft)
        if cfg is not None:
            return cfg
        last_errors = errors
        if _deterministic_repairs(draft, errors):
            continue
        if llm_repair is not None:
            draft = llm_repair(draft, errors)
            continue
        break
    raise ConfigValidationError(last_errors, draft)
