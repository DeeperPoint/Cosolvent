"""Integration flows across auth, onboarding, admin, discovery, and chat."""

from __future__ import annotations

import pytest

from tests.e2e.helpers import (
    bootstrap_or_login_admin,
    get_base_url,
    new_client,
    random_email,
    register_update_submit,
    require_mode,
    signup_user,
    wait_for,
)

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "ChangeMe123!"
USER_PASSWORD = "UserPass123!"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_onboarding_admin_discovery_and_communication_roundtrip():
    require_mode("RUN_INTEGRATION")
    base_url = get_base_url("INTEGRATION_BASE_URL")

    admin = new_client(base_url)
    producer = new_client(base_url)
    buyer = new_client(base_url)
    anonymous = new_client(base_url)
    intruder = new_client(base_url)

    try:
        await bootstrap_or_login_admin(admin, ADMIN_EMAIL, ADMIN_PASSWORD)

        producer_auth = await signup_user(
            producer,
            email=random_email("producer"),
            password=USER_PASSWORD,
            participant_type="producer",
        )
        producer_submit = await register_update_submit(
            producer,
            "producer",
            {
                "farm_name": "North Ridge Farm",
                "country": "Canada",
                "primary_crops": ["Wheat"],
            },
        )
        assert producer_submit["status"] == "pending_review"

        apps = await admin.get("/api/admin/applications", params={"status": "pending"})
        apps.raise_for_status()
        app_items = apps.json()
        assert app_items, "Expected at least one pending application"
        producer_app = next(
            (item for item in app_items if item.get("user_id") == producer_auth["user_id"]),
            None,
        )
        assert producer_app, "Expected pending application for producer"
        app_id = producer_app["id"]

        approved = await admin.post(f"/api/admin/applications/{app_id}/approve")
        approved.raise_for_status()
        approved_body = approved.json()
        assert approved_body["status"] == "approved"
        assert approved_body.get("profile_id")

        producer_alias = await producer.get("/api/roles/producer/me")
        producer_alias.raise_for_status()
        assert producer_alias.json().get("participant_type") == "producer"

        buyer_auth = await signup_user(
            buyer,
            email=random_email("buyer"),
            password=USER_PASSWORD,
            participant_type="buyer",
        )
        buyer_submit = await register_update_submit(
            buyer,
            "buyer",
            {
                "org_name": "Atlas Milling",
                "country": "Canada",
                "business_type": "Mill",
            },
        )
        assert buyer_submit["status"] == "active"

        buyer_alias = await buyer.get("/api/roles/buyer/me")
        buyer_alias.raise_for_status()
        assert buyer_alias.json().get("participant_type") == "buyer"

        anon_search_resp = await anonymous.post(
            "/api/search/producer",
            json={"query": "wheat farm", "filters": {"country": "Canada"}},
        )
        assert anon_search_resp.status_code == 401

        forbidden_search = await producer.post(
            "/api/search/producer",
            json={"query": "wheat farm", "filters": {"country": "Canada"}},
        )
        assert forbidden_search.status_code == 403

        async def _search_producer():
            resp = await buyer.post(
                "/api/search/producer",
                json={"query": "wheat farm", "filters": {"country": "Canada"}},
            )
            resp.raise_for_status()
            return resp.json()

        search_data = await wait_for(
            _search_producer,
            lambda body: bool(body.get("results")),
            timeout_seconds=20.0,
            interval_seconds=0.5,
        )
        assert search_data["results"], "Expected producer search results"

        create_conv = await buyer.post(
            "/api/conversations",
            json={
                "receiver_user_id": producer_auth["user_id"],
                "initial_message": "Interested in your wheat specs",
            },
        )
        create_conv.raise_for_status()
        conv = create_conv.json()
        conv_id = conv["id"]
        assert conv["status"] in {"pending", "active"}

        producer_notifications = await producer.get("/api/notifications")
        producer_notifications.raise_for_status()
        notif_types = [n.get("type") for n in producer_notifications.json()]
        assert "chat_request" in notif_types

        accept_conv = await producer.post(f"/api/conversations/{conv_id}/accept")
        accept_conv.raise_for_status()
        assert accept_conv.json()["status"] == "active"

        send_message = await buyer.post(
            f"/api/conversations/{conv_id}/messages",
            json={"content": "Can you share protein content range?", "content_type": "text"},
        )
        send_message.raise_for_status()
        first_message_id = send_message.json()["id"]

        create_conv_2 = await buyer.post(
            "/api/conversations",
            json={
                "receiver_user_id": producer_auth["user_id"],
                "initial_message": "Second thread",
            },
        )
        create_conv_2.raise_for_status()
        conv_2 = create_conv_2.json()
        conv_id_2 = conv_2["id"]
        if conv_2["status"] == "pending":
            accept_conv_2 = await producer.post(f"/api/conversations/{conv_id_2}/accept")
            accept_conv_2.raise_for_status()

        second_message = await buyer.post(
            f"/api/conversations/{conv_id_2}/messages",
            json={"content": "Message in second conversation", "content_type": "text"},
        )
        second_message.raise_for_status()
        second_message_id = second_message.json()["id"]

        mismatch_edit = await buyer.put(
            f"/api/conversations/{conv_id}/messages/{second_message_id}",
            json={"content": "attempted cross-thread edit"},
        )
        assert mismatch_edit.status_code == 404

        mismatch_delete = await buyer.delete(
            f"/api/conversations/{conv_id}/messages/{second_message_id}",
        )
        assert mismatch_delete.status_code == 404

        intruder_auth = await signup_user(
            intruder,
            email=random_email("intruder"),
            password=USER_PASSWORD,
            participant_type="buyer",
        )
        assert intruder_auth["user_id"]

        intruder_edit = await intruder.put(
            f"/api/conversations/{conv_id}/messages/{first_message_id}",
            json={"content": "intruder-edit"},
        )
        assert intruder_edit.status_code == 403

        intruder_delete = await intruder.delete(
            f"/api/conversations/{conv_id}/messages/{first_message_id}",
        )
        assert intruder_delete.status_code == 403

        producer_notifications_2 = await producer.get("/api/notifications")
        producer_notifications_2.raise_for_status()
        notif_types_after = [n.get("type") for n in producer_notifications_2.json()]
        assert "new_message" in notif_types_after

        deactivated = await admin.post(f"/api/admin/users/{buyer_auth['user_id']}/deactivate")
        deactivated.raise_for_status()

        verify = await buyer.get("/api/auth/verify")
        assert verify.status_code == 403
    finally:
        await admin.aclose()
        await producer.aclose()
        await buyer.aclose()
        await anonymous.aclose()
        await intruder.aclose()
