"""Full-stack lifecycle e2e — every public endpoint in order, every table populated.

This is the single "prove it works" test. Rather than unit-style
independent tests, it walks the product front-to-back:

1.  Health + setup probes.
2.  Admin bootstrap + admin-only inspection endpoints.
3.  Signup two end users (producer + buyer).
4.  Register → update draft → upload onboarding docs → submit draft.
5.  Admin lists pending applications and approves both.
6.  Each user fetches their own profile; updates it; lists the other
    participant type's public profile.
7.  Producer initiates a conversation with the buyer; buyer accepts;
    both exchange messages (text, edit, delete, share-assets).
8.  Admin inspects conversations + messages oversight.
9.  Admin manages FAQs (CRUD) and AI settings/prompts/documents.
10. Discovery search (global + scoped).
11. Notifications inbox for one user; mark-read.
12. Role-alias routes (``/api/roles/{slug}/...``) exercised for both
    participant types.
13. Admin admin-ops: list/get/role/deactivate/activate users;
    profile-status override.
14. File cleanup + logout.

After the run, ``REQUIRED_TABLES`` in
``tests/e2e/contract/db_coverage.py`` are asserted to each have at
least one row, proving every wired table is actually written by the
public API.

AI-specific tables (``ai_chat_threads``/``ai_chat_messages``) and the
orphan tables (``private_assets``, ``conversation_participants``,
``ai_chat_history``) are reported as informational but not required.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

from tests.e2e.contract.db_coverage import (
    OPTIONAL_TABLES,
    REQUIRED_TABLES,
    all_counts,
    assert_required_tables_populated,
)
from tests.e2e.helpers import (
    bootstrap_or_login_admin,
    get_base_url,
    new_client,
    random_email,
    register_update_submit,
    require_mode,
    signup_user,
)

_USER_PASSWORD = "UserPass123!"
_ADMIN_EMAIL = os.getenv("E2E_ADMIN_EMAIL", "admin@example.com")
_ADMIN_PASSWORD = os.getenv("E2E_ADMIN_PASSWORD", "ChangeMe123!")


def _assert_ok(resp: httpx.Response, *, label: str, codes: tuple[int, ...] = (200, 201, 204)) -> None:
    assert resp.status_code in codes, (
        f"[{label}] unexpected {resp.status_code}: "
        f"{resp.text[:400]}"
    )


async def _approve_if_pending(admin: httpx.AsyncClient, user_id: str) -> str | None:
    """Approve the pending application for ``user_id`` if one exists.

    Participant types with ``requires_approval: false`` auto-transition
    to active at submit-time; in that case there is no application row
    to approve and we return ``None``.
    """

    r = await admin.get("/api/admin/applications", params={"status": "pending"})
    _assert_ok(r, label="list applications")
    pending = r.json()
    row = next((a for a in pending if a.get("user_id") == user_id), None)
    if row is None:
        return None
    approve = await admin.post(f"/api/admin/applications/{row['id']}/approve")
    _assert_ok(approve, label=f"approve application {row['id']}")
    return approve.json().get("profile_id") or row["id"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_lifecycle_populates_every_table() -> None:
    require_mode("RUN_E2E")
    base_url = get_base_url("E2E_BASE_URL")

    admin = new_client(base_url)
    producer = new_client(base_url)
    buyer = new_client(base_url)
    anon = new_client(base_url)

    try:
        # ── Phase 1: Health & admin bootstrap ──
        r = await anon.get("/api/health")
        _assert_ok(r, label="health")

        r = await anon.get("/onboarding")
        _assert_ok(r, label="onboarding panel")

        r = await anon.get("/api/setup/config-template")
        _assert_ok(r, label="config template")

        r = await anon.get("/api/setup/presets")
        _assert_ok(r, label="setup presets")

        await bootstrap_or_login_admin(admin, _ADMIN_EMAIL, _ADMIN_PASSWORD)

        r = await admin.get("/api/auth/me")
        _assert_ok(r, label="admin me")
        admin_user = r.json()
        assert admin_user.get("role") == "admin"

        r = await admin.get("/api/auth/verify")
        _assert_ok(r, label="verify admin session")

        r = await admin.get("/api/admin/dashboard")
        _assert_ok(r, label="admin dashboard")

        r = await admin.get("/api/admin/config")
        _assert_ok(r, label="admin config summary")

        # ── Phase 2: Signup producer + buyer ──
        suffix = uuid.uuid4().hex[:8]
        producer_auth = await signup_user(
            producer,
            email=random_email(f"life-prod-{suffix}"),
            password=_USER_PASSWORD,
            participant_type="producer",
        )
        buyer_auth = await signup_user(
            buyer,
            email=random_email(f"life-buy-{suffix}"),
            password=_USER_PASSWORD,
            participant_type="buyer",
        )

        # ── Phase 3: Onboarding flow (register → draft → submit) ──
        await register_update_submit(
            producer,
            "producer",
            {
                "farm_name": "Lifecycle Farm",
                "country": "Canada",
                "primary_crops": ["Wheat"],
            },
        )
        await register_update_submit(
            buyer,
            "buyer",
            {
                "org_name": "Lifecycle Trading",
                "country": "Canada",
                "business_type": "Trading Company",
            },
        )

        # ── Phase 4: Admin approves applications that need it ──
        # (producers require approval; buyers are auto-approved per YAML.)
        await _approve_if_pending(admin, producer_auth["user_id"])
        await _approve_if_pending(admin, buyer_auth["user_id"])

        # Also exercise the reject path on a throwaway producer so the
        # application table has both "approved" and "rejected" rows.
        rej_producer = new_client(base_url)
        try:
            rej_auth = await signup_user(
                rej_producer,
                email=random_email(f"life-rej-{suffix}"),
                password=_USER_PASSWORD,
                participant_type="producer",
            )
            await register_update_submit(
                rej_producer,
                "producer",
                {
                    "farm_name": "Reject Farm",
                    "country": "USA",
                    "primary_crops": ["Wheat"],
                },
            )
            apps = await admin.get(
                "/api/admin/applications", params={"status": "pending"}
            )
            _assert_ok(apps, label="list pending before reject")
            rej_row = next(
                (a for a in apps.json() if a.get("user_id") == rej_auth["user_id"]),
                None,
            )
            if rej_row is not None:
                rj = await admin.post(
                    f"/api/admin/applications/{rej_row['id']}/reject",
                    json={"feedback": "lifecycle reject path"},
                )
                _assert_ok(rj, label="reject application")
        finally:
            await rej_producer.aclose()

        # ── Phase 5: Profile CRUD by owner + public read ──
        r = await producer.get("/api/profiles/producer/me")
        _assert_ok(r, label="producer me")
        prod_me = r.json()

        r = await buyer.get("/api/profiles/buyer/me")
        _assert_ok(r, label="buyer me")
        buyer_me = r.json()
        buyer_profile_id = buyer_me["id"]

        r = await producer.get(f"/api/profiles/producer/{prod_me['id']}")
        _assert_ok(r, label="producer self-by-id")

        # Full-field update (profile validation requires all required fields).
        prod_fields = dict(prod_me.get("fields", {}))
        prod_fields["description"] = "Updated by lifecycle test"
        r = await producer.put(
            f"/api/profiles/producer/{prod_me['id']}",
            json={"fields": prod_fields},
        )
        _assert_ok(r, label="producer update profile")

        # Buyer views producer's public profile (different slug path).
        r = await buyer.get(f"/api/profiles/producer/{prod_me['id']}")
        _assert_ok(r, label="buyer views producer profile")

        # ── Phase 6: File upload (public + private) ──
        up = await producer.post(
            "/api/files/upload",
            data={"privacy": "public", "category": "asset", "profile_id": prod_me["id"]},
            files={"file": ("public.txt", b"public-asset", "text/plain")},
        )
        _assert_ok(up, label="producer file upload")
        file_id = up.json().get("id") or up.json().get("_id")
        assert file_id

        r = await producer.get(f"/api/files/{file_id}")
        _assert_ok(r, label="producer get uploaded file")

        # ── Phase 7: Conversation (buyer → producer per YAML rules) ──
        conv_resp = await buyer.post(
            "/api/conversations",
            json={
                "receiver_user_id": producer_auth["user_id"],
                "initial_message": "Hello from lifecycle test",
            },
        )
        _assert_ok(conv_resp, label="create conversation", codes=(200, 201))
        conv = conv_resp.json()
        conv_id = conv["id"]

        # Producer accepts per requires_approval: true.
        r = await producer.post(f"/api/conversations/{conv_id}/accept")
        _assert_ok(r, label="producer accepts conversation")

        msg = await producer.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": "Nice to meet you!", "content_type": "text"},
        )
        _assert_ok(msg, label="producer sends message", codes=(200, 201))
        msg_id = msg.json()["id"]

        r = await producer.put(
            f"/api/conversations/{conv_id}/messages/{msg_id}",
            json={"content": "Nice to meet you (edited)"},
        )
        _assert_ok(r, label="producer edits message")

        r = await producer.get(f"/api/conversations/{conv_id}/messages")
        _assert_ok(r, label="list messages")

        r = await buyer.get("/api/conversations")
        _assert_ok(r, label="buyer lists conversations")

        r = await buyer.get(f"/api/conversations/{conv_id}")
        _assert_ok(r, label="buyer gets conversation")

        share = await buyer.post(
            f"/api/conversations/{conv_id}/share-assets",
            json={"asset_ids": [file_id]},
        )
        _assert_ok(share, label="buyer shares assets")

        # Second message before we mutate/delete, so messages table stays populated.
        extra_msg = await buyer.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": "second", "content_type": "text"},
        )
        _assert_ok(extra_msg, label="buyer second message", codes=(200, 201))

        r = await producer.delete(f"/api/conversations/{conv_id}/messages/{msg_id}")
        _assert_ok(r, label="producer deletes their message")

        r = await admin.get("/api/admin/conversations", params={"limit": 10})
        _assert_ok(r, label="admin lists conversations")

        r = await admin.get(f"/api/admin/conversations/{conv_id}/messages")
        _assert_ok(r, label="admin inspects conversation messages")

        # ── Phase 8: Admin FAQ CRUD ──
        faq = await admin.post(
            "/api/admin/faqs",
            json={"question": "What is this?", "answer": "A lifecycle test.", "sort_order": 1},
        )
        _assert_ok(faq, label="create faq", codes=(200, 201))
        faq_id = faq.json().get("id") or faq.json().get("_id")
        assert faq_id

        r = await admin.get("/api/admin/faqs")
        _assert_ok(r, label="list faqs")

        r = await admin.get(f"/api/admin/faqs/{faq_id}")
        _assert_ok(r, label="get faq")

        r = await admin.put(
            f"/api/admin/faqs/{faq_id}",
            json={"answer": "An updated lifecycle test."},
        )
        _assert_ok(r, label="update faq")

        # Create a second FAQ so the table still has rows after DELETE.
        faq2 = await admin.post(
            "/api/admin/faqs",
            json={"question": "Keep me", "answer": "I stay", "sort_order": 2},
        )
        _assert_ok(faq2, label="create second faq", codes=(200, 201))

        r = await admin.delete(f"/api/admin/faqs/{faq_id}")
        _assert_ok(r, label="delete first faq")

        # ── Phase 9: AI settings/prompts/documents ──
        r = await admin.get("/api/ai/settings")
        _assert_ok(r, label="get ai settings")
        original_settings = r.json() or {}

        r = await admin.put("/api/ai/settings", json={"temperature": 0.5})
        _assert_ok(r, label="update ai settings")

        r = await admin.get("/api/ai/prompts")
        _assert_ok(r, label="list ai prompts")

        r = await admin.put(
            "/api/ai/prompts/rag_query",
            json={"template": "{context}\n\nQuestion: {question}\n\nAnswer:"},
        )
        _assert_ok(r, label="update ai prompt")

        r = await admin.get("/api/ai/providers")
        _assert_ok(r, label="ai providers")

        r = await admin.get("/api/ai/models")
        _assert_ok(r, label="ai models")

        # Best-effort document upload; skip body-level test if embedding fails
        # (no API key configured).
        doc_resp = await admin.post(
            "/api/ai/documents",
            json={
                "filename": "lifecycle.txt",
                "content": "Lifecycle test content.",
                "content_type": "text/plain",
            },
        )
        doc_id: str | None = None
        if doc_resp.status_code in (200, 201):
            doc_id = doc_resp.json().get("id") or doc_resp.json().get("_id")
            r = await admin.get("/api/ai/documents")
            _assert_ok(r, label="list ai documents")
            if doc_id:
                # Keep one document alive so the table stays populated.
                pass

        # Mirror the same listing on /api/admin/ai/* to exercise those routes.
        r = await admin.get("/api/admin/ai/settings")
        _assert_ok(r, label="admin ai settings")
        r = await admin.get("/api/admin/ai/providers")
        _assert_ok(r, label="admin ai providers")
        r = await admin.get("/api/admin/ai/models")
        _assert_ok(r, label="admin ai models")
        r = await admin.get("/api/admin/ai/prompts")
        _assert_ok(r, label="admin ai prompts")
        r = await admin.get("/api/admin/ai/documents")
        _assert_ok(r, label="admin ai documents")

        # Restore prior temperature if present.
        if "temperature" in original_settings:
            await admin.put(
                "/api/ai/settings",
                json={"temperature": original_settings["temperature"]},
            )

        # ── Phase 10: Discovery (buyer has can_search, producer does not) ──
        r = await buyer.post("/api/search", json={"query": "wheat", "page": 1, "page_size": 10})
        _assert_ok(r, label="global search")
        r = await buyer.post(
            "/api/search/producer", json={"query": "farm", "page": 1, "page_size": 10}
        )
        _assert_ok(r, label="scoped search")

        # ── Phase 11: Notifications ──
        r = await buyer.get("/api/notifications")
        _assert_ok(r, label="buyer notifications list")
        buyer_notifs = r.json()
        if buyer_notifs:
            notif_id = (buyer_notifs[0].get("id") or buyer_notifs[0].get("_id"))
            if notif_id:
                r = await buyer.put(f"/api/notifications/{notif_id}/read")
                _assert_ok(r, label="mark notification read")

        # ── Phase 12: Role-alias routes ──
        # GETs on both role-alias surfaces to cover the alias router.
        r = await producer.get("/api/roles/producer/me")
        _assert_ok(r, label="role alias producer me")
        r = await buyer.get("/api/roles/buyer/me")
        _assert_ok(r, label="role alias buyer me")

        r = await producer.get(f"/api/roles/producer/{prod_me['id']}")
        _assert_ok(r, label="role alias producer by id")

        r = await buyer.get(f"/api/roles/buyer/{buyer_me['id']}")
        _assert_ok(r, label="role alias buyer by id")

        # ── Phase 13: Admin user + profile management ──
        r = await admin.get("/api/admin/users", params={"limit": 20})
        _assert_ok(r, label="admin list users")

        r = await admin.get(f"/api/admin/users/{buyer_auth['user_id']}")
        _assert_ok(r, label="admin get buyer user")

        r = await admin.post(f"/api/admin/users/{buyer_auth['user_id']}/deactivate")
        _assert_ok(r, label="admin deactivate buyer")

        r = await admin.post(f"/api/admin/users/{buyer_auth['user_id']}/activate")
        _assert_ok(r, label="admin reactivate buyer")

        r = await admin.get(f"/api/admin/profiles/{buyer_profile_id}")
        _assert_ok(r, label="admin get profile")

        r = await admin.put(
            f"/api/admin/profiles/{buyer_profile_id}/status",
            json={"status": "active"},
        )
        _assert_ok(r, label="admin profile status update")

        # Close the conversation before logout so conv lifecycle is complete.
        r = await buyer.post(f"/api/conversations/{conv_id}/close")
        _assert_ok(r, label="buyer closes conversation")

        # ── Phase 14: Logout (producer + buyer) ──
        r = await producer.post("/api/auth/logout")
        _assert_ok(r, label="producer logout")
        r = await buyer.post("/api/auth/logout")
        _assert_ok(r, label="buyer logout")

        # ── Verify every REQUIRED table is populated ──
        counts = await assert_required_tables_populated()
        # Sanity — each required table should have *exactly* at least one row.
        for name, n in counts.items():
            assert n >= 1, f"{name} is empty"

        full = await all_counts()
        # Print for the test log — makes it visible without failing.
        print("\n── DB table coverage ──")
        for name in REQUIRED_TABLES:
            print(f"  ✓ {name:<30} {full[name]:>6} rows (required)")
        for name in OPTIONAL_TABLES:
            status = "populated" if full[name] else "empty (optional)"
            print(f"  · {name:<30} {full[name]:>6} rows ({status})")
    finally:
        for c in (admin, producer, buyer, anon):
            await c.aclose()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_lifecycle_contract_every_response_is_valid_json(
    admin_client: httpx.AsyncClient,
) -> None:
    """Smoke: every JSON-returning route should return parseable JSON.

    This exercises the response-model contract. We sample one endpoint
    per module; ``ContractClient`` fixtures do the full schema check
    across the module-specific suites.
    """

    require_mode("RUN_E2E")

    sample: list[tuple[str, str]] = [
        ("GET", "/api/admin/dashboard"),
        ("GET", "/api/admin/config"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/applications"),
        ("GET", "/api/admin/faqs"),
        ("GET", "/api/admin/conversations"),
        ("GET", "/api/admin/ai/providers"),
        ("GET", "/api/admin/ai/settings"),
        ("GET", "/api/admin/ai/prompts"),
        ("GET", "/api/ai/providers"),
        ("GET", "/api/ai/settings"),
        ("GET", "/api/ai/prompts"),
        ("GET", "/api/notifications"),
    ]
    for method, path in sample:
        r = await admin_client.request(method, path)
        _assert_ok(r, label=f"sample {method} {path}")
        try:
            _ = r.json()
        except Exception as exc:  # pragma: no cover - defensive
            raise AssertionError(
                f"{method} {path} did not return valid JSON: {exc}"
            ) from exc


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_db_coverage_report_is_emitted() -> None:
    """Write a compact DB coverage report so the CI log shows table counts.

    Runs independently of the full lifecycle; useful when the lifecycle
    test is skipped but we still want a view of the state.
    """

    require_mode("RUN_E2E")

    counts = await all_counts()
    header = f"{'table':<30} {'rows':>8}"
    lines = [header, "-" * len(header)]
    for name in REQUIRED_TABLES + OPTIONAL_TABLES:
        lines.append(f"{name:<30} {counts[name]:>8}")
    print("\n" + "\n".join(lines))
