"""
Test discovery and notification APIs with real credentials.

Usage:
  python scripts/test_discovery_notifications.py [--base-url http://localhost:18000]
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urljoin

import httpx

BASE = "http://localhost:18000"

USERS = [
    {"name": "admin", "email": "admin@testpgp.com", "password": "pass1234"},
    {"name": "producer", "email": "disc_producer@farm.com", "password": "Farmer123!"},
    {"name": "buyer", "email": "disc_buyer@trade.com", "password": "Buyer123!"},
]


def request(client: httpx.Client, method: str, url: str, body: dict | None = None, timeout: float = 15):
    kwargs = {"timeout": timeout}
    if body is not None:
        kwargs["json"] = body
    r = client.request(method, url, **kwargs)
    try:
        return r.status_code, r.json()
    except json.JSONDecodeError:
        return r.status_code, r.text


def login(base_url: str, email: str, password: str) -> tuple[httpx.Client | None, str | None]:
    """Return (client with session cookies, None) or (None, error)."""
    url = urljoin(base_url, "/api/auth/login")
    with httpx.Client(base_url=base_url, follow_redirects=True) as client:
        r = client.post(url, json={"email": email, "password": password})
        if r.status_code != 200:
            return None, f"login failed: {r.status_code} {r.text[:500]}"
        # Server sets session_token with Secure=True; over HTTP clients may not send it.
        # Send it explicitly for localhost testing.
        session_token = r.cookies.get("session_token")
        if not session_token:
            return None, "no session_token cookie in response"
        headers = {"Cookie": f"session_token={session_token}"}
    # New client that sends the cookie on every request (for http:// localhost)
    client = httpx.Client(base_url=base_url, follow_redirects=True, headers=headers, timeout=15.0)
    return client, None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default=BASE)
    args = p.parse_args()
    base = args.base_url.rstrip("/")

    results = []

    # ---- Discovery ----
    # Anonymous: expect 401 when anonymous_search_enabled is false
    with httpx.Client(base_url=base, follow_redirects=True) as anon:
        code, data = request(anon, "POST", urljoin(base, "/api/search"), {"page": 1, "page_size": 10})
    results.append(
        ("discovery", "POST /api/search (anonymous)", code, code == 401, data if code != 401 else "OK")
    )

    with httpx.Client(base_url=base, follow_redirects=True) as anon:
        code2, data2 = request(anon, "POST", urljoin(base, "/api/search/producer"), {"page": 1, "page_size": 10})
    results.append(
        ("discovery", "POST /api/search/producer (anonymous)", code2, code2 == 401, data2 if code2 != 401 else "OK")
    )

    # Producer has can_search: false → expect 403
    client_prod, err = login(base, USERS[1]["email"], USERS[1]["password"])
    if err:
        results.append(("auth", "producer login", 0, False, err))
    else:
        try:
            code3, data3 = request(client_prod, "POST", urljoin(base, "/api/search"), {"page": 1, "page_size": 10})
            results.append(
                ("discovery", "POST /api/search (producer)", code3, code3 == 403, data3 if code3 != 403 else "OK")
            )
        finally:
            client_prod.close()

    # Buyer has can_search: true → expect 200 and { results, total, page, page_size }
    client_buyer, err = login(base, USERS[2]["email"], USERS[2]["password"])
    if err:
        results.append(("auth", "buyer login", 0, False, err))
    else:
        try:
            code4, data4 = request(client_buyer, "POST", urljoin(base, "/api/search"), {"page": 1, "page_size": 10})
            ok4 = code4 == 200 and isinstance(data4, dict) and "results" in data4 and "total" in data4
            results.append(
                ("discovery", "POST /api/search (buyer)", code4, ok4, data4 if not ok4 else "OK")
            )
            code5, data5 = request(
                client_buyer, "POST", urljoin(base, "/api/search/producer"), {"page": 1, "page_size": 5}
            )
            ok5 = code5 == 200 and isinstance(data5, dict) and "results" in data5
            results.append(
                ("discovery", "POST /api/search/producer (buyer)", code5, ok5, data5 if not ok5 else "OK")
            )
        finally:
            client_buyer.close()

    # ---- Notifications (require auth) ----
    for user in USERS:
        client, err = login(base, user["email"], user["password"])
        if err:
            results.append(("auth", f"{user['name']} login", 0, False, err))
            continue
        try:
            # GET /api/notifications
            code, data = request(client, "GET", urljoin(base, "/api/notifications?skip=0&limit=10"))
            results.append(
                ("notifications", f"GET /api/notifications ({user['name']})", code, code == 200, data if code != 200 else "OK")
            )
            # PUT /api/notifications/{id}/read — use a UUID; expect 404 if not found
            code_put, data_put = request(
                client,
                "PUT",
                urljoin(base, "/api/notifications/00000000-0000-0000-0000-000000000000/read"),
            )
            # 200 = marked read, 404 = not found (both acceptable)
            results.append(
                (
                    "notifications",
                    f"PUT .../read ({user['name']})",
                    code_put,
                    code_put in (200, 404),
                    data_put if code_put not in (200, 404) else "OK",
                )
            )
        finally:
            client.close()

    # Report
    failed = [r for r in results if not r[3]]
    for module, label, status, ok, detail in results:
        status_str = str(status) if status else "error"
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} [{module}] {label} → {status_str}")
        if not ok and detail != "OK":
            print(f"      {detail}")
    print()
    if failed:
        print(f"Failed: {len(failed)} / {len(results)}")
        sys.exit(1)
    print(f"All {len(results)} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
