"""
OpenAPI-driven API smoke test.

Goal: hit every documented endpoint at least once and flag unexpected 5xx errors.
This is not a full contract test suite; it focuses on availability/stability.

Usage:
  python3 scripts/api_smoke.py --base-url http://localhost:18000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any


DEFAULT_USERS: dict[str, dict[str, str]] = {
    "admin": {"email": "admin@testpgp.com", "password": "pass1234"},
    "producer_disc": {"email": "disc_producer@farm.com", "password": "Farmer123!"},
    "producer_comm": {"email": "comm_producer@farm.com", "password": "Farmer123!"},
    "buyer_disc": {"email": "disc_buyer@trade.com", "password": "Buyer123!"},
    "buyer_comm": {"email": "comm_buyer@trade.com", "password": "Buyer123!"},
}


@dataclass(frozen=True)
class Client:
    name: str
    opener: urllib.request.OpenerDirector


def _json_request(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    json_body: dict[str, Any] | None = None,
    timeout_s: float = 20.0,
) -> tuple[int, dict[str, str], bytes]:
    data = None
    headers = {"Accept": "application/json"}
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=data, method=method, headers=headers)
    try:
        with opener.open(req, timeout=timeout_s) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except urllib.error.HTTPError as e:
        # HTTPError is also a response object
        body = b""
        try:
            body = e.read()
        except Exception:
            body = b""
        return int(e.code), dict(e.headers.items()), body


def _make_client(name: str) -> Client:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    return Client(name=name, opener=opener)


def _login(base_url: str, client: Client, email: str, password: str) -> bool:
    url = urllib.parse.urljoin(base_url, "/api/auth/login")
    status, _, body = _json_request(
        client.opener,
        method="POST",
        url=url,
        json_body={"email": email, "password": password},
        timeout_s=20.0,
    )
    if status != 200:
        sys.stderr.write(f"[login] {client.name} failed: {status} body={body[:2000]!r}\n")
        return False
    return True


def _fetch_openapi(base_url: str) -> dict[str, Any]:
    url = urllib.parse.urljoin(base_url, "/openapi.json")
    opener = urllib.request.build_opener()
    status, _, body = _json_request(opener, method="GET", url=url, json_body=None, timeout_s=20.0)
    if status != 200:
        raise RuntimeError(f"Failed to fetch OpenAPI spec: {status} {body[:2000]!r}")
    return json.loads(body.decode("utf-8"))


def _dummy_path_params(path: str) -> str:
    # Substitute {param} placeholders with reasonably-shaped dummy values.
    # We don't know types from the path string alone; pick a UUID-ish value which works often.
    dummy_uuid = "00000000-0000-0000-0000-000000000000"

    out = ""
    i = 0
    while i < len(path):
        if path[i] == "{":
            j = path.find("}", i + 1)
            if j == -1:
                out += path[i:]
                break
            name = path[i + 1 : j].lower()
            if any(k in name for k in ["id", "uuid", "doc", "conv", "message", "profile", "file"]):
                out += dummy_uuid
            elif any(k in name for k in ["page", "limit", "offset", "count", "n", "k"]):
                out += "1"
            else:
                out += "test"
            i = j + 1
        else:
            out += path[i]
            i += 1
    return out


def _guess_body(spec_op: dict[str, Any]) -> dict[str, Any] | None:
    request_body = spec_op.get("requestBody")
    if not request_body:
        return None
    content = (request_body.get("content") or {}).get("application/json")
    if not content:
        # For multipart/form-data or other types, just omit body and allow 4xx.
        return None
    schema = content.get("schema") or {}
    # Minimal body: {} is usually enough to get a validation error (422) instead of 500.
    if schema.get("type") == "object":
        return {}
    return {}


def _should_test_with(role: str, path: str) -> bool:
    if path.startswith("/api/admin/"):
        return role == "admin"
    # For non-admin endpoints, test with all authenticated roles.
    if role == "admin":
        return True
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:18000")
    parser.add_argument("--timeout-s", type=float, default=20.0)
    parser.add_argument("--sleep-ms", type=int, default=0)
    args = parser.parse_args()

    base_url: str = args.base_url.rstrip("/")

    spec = _fetch_openapi(base_url)
    paths: dict[str, Any] = spec.get("paths") or {}

    clients: dict[str, Client] = {
        "anonymous": _make_client("anonymous"),
        "admin": _make_client("admin"),
        "producer": _make_client("producer"),
        "buyer": _make_client("buyer"),
    }

    # Authenticate (best-effort; keep going even if a user fails).
    ok_admin = _login(base_url, clients["admin"], **DEFAULT_USERS["admin"])
    ok_prod = _login(base_url, clients["producer"], **DEFAULT_USERS["producer_disc"])
    ok_buyer = _login(base_url, clients["buyer"], **DEFAULT_USERS["buyer_disc"])
    if not ok_admin:
        sys.stderr.write("[warn] admin login failed; admin-only endpoints may report 401/403.\n")
    if not ok_prod:
        sys.stderr.write("[warn] producer login failed; producer checks may report 401/403.\n")
    if not ok_buyer:
        sys.stderr.write("[warn] buyer login failed; buyer checks may report 401/403.\n")

    methods_order = ["get", "post", "put", "patch", "delete", "options", "head"]

    total = 0
    failures: list[dict[str, Any]] = []
    stats: dict[str, int] = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "net": 0}

    def record(status: int | None) -> None:
        if status is None:
            stats["net"] += 1
            return
        if 200 <= status < 300:
            stats["2xx"] += 1
        elif 300 <= status < 400:
            stats["3xx"] += 1
        elif 400 <= status < 500:
            stats["4xx"] += 1
        elif 500 <= status < 600:
            stats["5xx"] += 1

    for path, item in sorted(paths.items()):
        for method in methods_order:
            if method not in item:
                continue

            op = item[method] or {}
            # Skip WebSocket-ish endpoints (rare in OpenAPI here, but be safe).
            if path.startswith("/ws") or "websocket" in (op.get("summary") or "").lower():
                continue

            for role, client in clients.items():
                if not _should_test_with(role if role != "anonymous" else "anonymous", path):
                    continue
                if role == "anonymous" and path.startswith("/api/admin/"):
                    # Admin endpoints should be forbidden for anonymous; no need to spam.
                    continue

                total += 1
                substituted = _dummy_path_params(path)
                url = urllib.parse.urljoin(base_url, substituted)
                body = _guess_body(op) if method in {"post", "put", "patch"} else None

                try:
                    status, _, resp_body = _json_request(
                        client.opener,
                        method=method.upper(),
                        url=url,
                        json_body=body,
                        timeout_s=float(args.timeout_s),
                    )
                    record(status)

                    if 500 <= status < 600:
                        failures.append(
                            {
                                "role": role,
                                "method": method.upper(),
                                "path": path,
                                "url": url,
                                "status": status,
                                "body_preview": resp_body[:2000].decode("utf-8", errors="replace"),
                            }
                        )
                except Exception as e:
                    record(None)
                    failures.append(
                        {
                            "role": role,
                            "method": method.upper(),
                            "path": path,
                            "url": url,
                            "status": None,
                            "error": repr(e),
                        }
                    )

                if args.sleep_ms:
                    time.sleep(args.sleep_ms / 1000.0)

    print(json.dumps({"total_requests": total, "stats": stats, "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
