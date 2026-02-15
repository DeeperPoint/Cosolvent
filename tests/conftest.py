"""Shared test fixtures."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "test_config"


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
