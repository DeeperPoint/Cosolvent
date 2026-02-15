"""Tests for CLI config validation."""

from __future__ import annotations

from pathlib import Path

from cli.validate import validate_config_file

FIXTURES = Path(__file__).parent.parent / "test_config"


class TestValidateConfigFile:
    def test_agriculture_valid(self):
        assert validate_config_file(str(FIXTURES / "agriculture.yaml")) is True

    def test_minimal_valid(self):
        assert validate_config_file(str(FIXTURES / "minimal.yaml")) is True

    def test_nonexistent_path(self):
        assert validate_config_file("/nonexistent/path.yaml") is False

    def test_talent_valid(self):
        assert validate_config_file(str(FIXTURES / "talent.yaml")) is True
