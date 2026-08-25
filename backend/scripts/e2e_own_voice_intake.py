"""Live end-to-end check of own-voice intake against a running stack (GAP-11).

Exercises the real HTTP surface with a real model and a real database — no mocks.
Two of the defects found while building this were invisible to mocked tests (a
schema the provider rejected, and provenance stripped by the response projection),
which is the case for running this before a release rather than relying on unit
coverage alone.

    docker compose up -d
    INTEGRATION_BASE_URL=http://localhost:18000 python scripts/e2e_own_voice_intake.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

import httpx

BASE_URL = os.getenv("INTEGRATION_BASE_URL", "http://localhost:18000").rstrip("/")

# Demand side deliberately: buyer extraction was switched off before GAP-11, so this
# is the half that had never run.
PARTICIPANT_TYPE = os.getenv("E2E_PARTICIPANT_TYPE", "buyer")

PROSE = (
    "We're Northwind Automation, based in Hamilton Ontario. We need a machine shop that can "
    "hold tight tolerances on aluminium housings — roughly 400 parts a month, and we need "
    "AS9100 certification because these go into aerospace assemblies. Budget is around "
    "85 dollars an hour and we'd want first parts within six weeks."
)

failures: list[str] = []
notes: list[str] = []


def check(condition: bool, message: str) -> None:
    if condition:
        print(f"  PASS  {message}")
    else:
        print(f"  FAIL  {message}")
        failures.append(message)


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120.0) as client:
        print(f"Target: {BASE_URL}\n")

        health = await client.get("/api/health")
        if health.status_code != 200:
            print(f"Stack not reachable ({health.status_code}). Run: docker compose up -d")
            return 2

        # ── 1. Register a participant ────────────────────────────────────
        print("1. Signing up a participant")
        email = f"e2e-{uuid.uuid4().hex[:10]}@example.com"
        signup = await client.post(
            "/api/auth/signup",
            json={"email": email, "password": "e2e-password-123", "participant_type": PARTICIPANT_TYPE},
        )
        if signup.status_code != 200:
            print(f"  signup failed {signup.status_code}: {signup.text[:300]}")
            return 2
        check("session_token" in signup.cookies, "session cookie set")
        check(signup.json().get("access_token") is None, "access_token withheld unless opted in (GAP-1)")

        opted = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "e2e-password-123"},
            headers={"X-Auth-Mode": "bearer"},
        )
        token = opted.json().get("access_token")
        check(bool(token), "access_token returned when opted in")

        # A profile must exist before enrichment.
        await client.post(f"/api/profiles/{PARTICIPANT_TYPE}/register", json={"fields": {}})

        # ── 2. Own-voice intake ──────────────────────────────────────────
        print("\n2. Extracting canonical fields from prose")
        res = await client.post(f"/api/profiles/{PARTICIPANT_TYPE}/me/extract", json={"text": PROSE})
        if res.status_code != 200:
            print(f"  extract failed {res.status_code}: {res.text[:400]}")
            return 2
        body = res.json()
        print(json.dumps({k: body[k] for k in ("applied", "rejected", "low_confidence")}, indent=2))

        check(len(body["applied"]) > 0, f"canonical fields applied ({len(body['applied'])})")
        check(body.get("target") in ("draft", "profile"), f"target reported ({body.get('target')})")
        # Inferred values must not reach canonical fields — matching reads those.
        overlap = set(body["applied"]) & set(body.get("suggested", {}))
        check(not overlap, f"low-confidence values held back, not applied (overlap: {overlap})")
        check(body["strength_after"] >= body["strength_before"], "profile strength did not regress")
        check(isinstance(body["rejected"], list), "rejections reported as a list, not dropped silently")
        for entry in body["rejected"]:
            check("reason" in entry, f"rejection for '{entry.get('field')}' carries a reason")

        # ── 3. Dual representation persisted ─────────────────────────────
        print("\n3. Checking the raw half survived")
        # A newly registered participant has a draft, not a profile.
        endpoint = "draft" if body.get("target") == "draft" else "me"
        me = await client.get(f"/api/profiles/{PARTICIPANT_TYPE}/{endpoint}")
        check(me.status_code == 200, f"GET /{endpoint} readable ({me.status_code})")
        profile = me.json()
        intake = profile.get("_intake") or {}
        check(intake.get("raw_text") == PROSE, "raw submission preserved verbatim in _intake")
        check(bool(intake.get("fields")), "per-field provenance recorded")

        for name, entry in (intake.get("fields") or {}).items():
            conf = entry.get("confidence")
            check(
                isinstance(conf, (int, float)) and 0.0 <= conf <= 1.0,
                f"{name}: confidence {conf} in range",
            )

        # Values that landed must be schema-valid, which is what the enum guarantees.
        for name in body["applied"]:
            check(name in profile.get("fields", {}), f"{name} written to canonical fields")
        for name in body.get("suggested", {}):
            check(name not in profile.get("fields", {}), f"{name} correctly withheld from canonical fields")

        # ── 4. Provenance is owner-only ──────────────────────────────────
        print("\n4. Checking provenance is not exposed to other participants")
        other_email = f"e2e-other-{uuid.uuid4().hex[:8]}@example.com"
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as other:
            reg = await other.post(
                "/api/auth/signup",
                json={"email": other_email, "password": "e2e-password-123", "participant_type": PARTICIPANT_TYPE},
            )
            if reg.status_code == 200:
                seen = await other.get(f"/api/profiles/{PARTICIPANT_TYPE}/{profile['id']}")
                if seen.status_code == 200:
                    check(
                        (seen.json().get("_intake") is None),
                        "another participant cannot read the raw submission",
                    )
                else:
                    notes.append(f"cross-viewer read returned {seen.status_code}; visibility not exercised")
            else:
                notes.append(f"second signup returned {reg.status_code}; visibility not exercised")

        # ── 5. Clarify loop ──────────────────────────────────────────────
        print("\n5. Clarify loop")
        clarify = await client.get(f"/api/profiles/{PARTICIPANT_TYPE}/me/clarify")
        if clarify.status_code == 200:
            q = clarify.json()
            print(f"  question: {q.get('question')}")
            check("question" in q, "clarify returns a question or completion")
            if q.get("current_value") is not None:
                check("is that right?" in (q.get("question") or ""), "low-confidence field asked as confirmation")
            else:
                notes.append("no low-confidence field this run; confirmation branch not exercised")
        else:
            check(False, f"clarify returned {clarify.status_code}")

        # ── 6. Extraction gate ───────────────────────────────────────────
        print("\n6. Onboarding gate")
        notes.append("all types have extraction enabled in this vertical; disabled path covered by unit tests")

    print("\n" + "=" * 64)
    for n in notes:
        print(f"NOTE: {n}")
    if failures:
        print(f"\n{len(failures)} CHECK(S) FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nALL CHECKS PASSED against the live stack")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
