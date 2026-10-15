"""Whether the compiled role aliases belong to the marketplace this process loaded.

The aliases under app/generated/ are compiled from one marketplace. Change
MARKETPLACE_CONFIG_PATH without recompiling — which is what happens when two
instances serve two verticals from one checkout — and they describe participant
types the loaded market does not have. They refuse every call in that state, so
the risk is not bad data but a misleading API surface, with the correct generic
routes hidden from the docs behind aliases that cannot work.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.marketplace_config import load_marketplace_config
from app.main import _stale_generated_roles

FIXTURES = Path(__file__).parent.parent / "test_config"


def _cfg(name):
    return load_marketplace_config(FIXTURES / name)


def test_nothing_is_stale_when_the_compiled_roles_are_this_market_s():
    cfg = _cfg("agriculture.yaml")
    slugs = [pt.slug for pt in cfg.participant_types]
    with patch("app.generated.role_registry.ROLE_SLUGS", slugs):
        assert _stale_generated_roles(cfg) == set()


def test_roles_from_another_market_are_reported_as_stale():
    cfg = _cfg("agriculture.yaml")
    with patch("app.generated.role_registry.ROLE_SLUGS", ["machine_shop", "quality_inspector"]):
        assert _stale_generated_roles(cfg) == {"machine_shop", "quality_inspector"}


def test_a_partial_overlap_still_counts_the_roles_that_do_not_belong():
    """Two markets sharing a slug name is not two markets sharing a schema: the
    one that does not belong is enough to make the compiled build the wrong one."""
    cfg = _cfg("agriculture.yaml")
    mine = [pt.slug for pt in cfg.participant_types]
    with patch("app.generated.role_registry.ROLE_SLUGS", mine + ["machine_shop"]):
        assert _stale_generated_roles(cfg) == {"machine_shop"}


def test_a_market_defining_more_types_than_were_compiled_is_not_stale():
    """Extra participant types mean missing aliases, not wrong ones. The compiled
    ones still describe types this market has, so they are left mounted."""
    cfg = _cfg("talent.yaml")
    with patch("app.generated.role_registry.ROLE_SLUGS", ["candidate"]):
        assert _stale_generated_roles(cfg) == set()


def test_a_build_without_a_role_registry_is_left_alone():
    """Nothing to compare against is not evidence of a mismatch."""
    cfg = _cfg("agriculture.yaml")
    with patch.dict("sys.modules", {"app.generated.role_registry": None}):
        assert _stale_generated_roles(cfg) == set()
