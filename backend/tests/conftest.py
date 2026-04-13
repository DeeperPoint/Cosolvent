"""Shared test fixtures."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "test_config"

# Ensure marketplace.yaml is resolvable when tests run from backend/
if "MARKETPLACE_CONFIG_PATH" not in os.environ:
    _root_yaml = Path(__file__).resolve().parent.parent.parent / "marketplace.yaml"
    _example_yaml = _root_yaml.with_name("marketplace.example.yaml")
    if _root_yaml.exists():
        os.environ["MARKETPLACE_CONFIG_PATH"] = str(_root_yaml)
    elif _example_yaml.exists():
        os.environ["MARKETPLACE_CONFIG_PATH"] = str(_example_yaml)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def agriculture_config_path() -> Path:
    return FIXTURES_DIR / "agriculture.yaml"


@pytest.fixture
def talent_config_path() -> Path:
    return FIXTURES_DIR / "talent.yaml"


@pytest.fixture
def minimal_config_path() -> Path:
    return FIXTURES_DIR / "minimal.yaml"
