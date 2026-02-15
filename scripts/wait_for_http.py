"""Wait for an HTTP endpoint to return 200."""

from __future__ import annotations

import argparse
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()

    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(args.url, timeout=5) as resp:
                if resp.status == 200:
                    print(f"Ready: {args.url}")
                    return 0
        except URLError:
            pass
        time.sleep(args.interval)

    print(f"Timed out waiting for {args.url}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
