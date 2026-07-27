"""Parse a C0 population file into raw records.

Accepts a top-level JSON list, or an object carrying the list under
``records`` / ``population`` / ``profiles``. Pure (no I/O) except the file read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_LIST_KEYS = ("records", "population", "profiles")


def parse_population_text(text: str) -> list[dict[str, Any]]:
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in _LIST_KEYS:
            if isinstance(data.get(key), list):
                return data[key]
        raise ValueError(f"population object must contain one of {_LIST_KEYS} as a list")
    raise ValueError("population file must be a JSON list or an object with a records list")


def load_population_file(path: str | Path) -> list[dict[str, Any]]:
    return parse_population_text(Path(path).read_text(encoding="utf-8"))
