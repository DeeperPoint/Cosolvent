"""Tests around app router registration strictness."""

from __future__ import annotations

from pathlib import Path


def test_main_does_not_suppress_import_errors():
    main_file = Path(__file__).parents[2] / "app" / "main.py"
    content = main_file.read_text()
    assert "except ImportError" not in content
