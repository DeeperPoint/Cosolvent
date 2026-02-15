"""Fail if integration/e2e suites are placeholders only."""

from __future__ import annotations

from pathlib import Path
import sys


def _suite_has_real_tests(path: Path) -> bool:
    for file in path.glob("test_*.py"):
        if file.name == "__init__.py":
            continue
        content = file.read_text().strip()
        if content:
            return True
    return False


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    integration = root / "tests" / "integration"
    e2e = root / "tests" / "e2e"

    failures: list[str] = []
    if not _suite_has_real_tests(integration):
        failures.append("tests/integration has no real test_*.py files")
    if not _suite_has_real_tests(e2e):
        failures.append("tests/e2e has no real test_*.py files")

    if failures:
        for failure in failures:
            print(f"[ERROR] {failure}")
        return 1

    print("Integration and E2E suites contain real tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
