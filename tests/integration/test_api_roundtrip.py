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
        app_id = app_items[0]["id"]

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

        search_resp = await buyer.post(
            "/api/search/producer",
            json={"query": "wheat farm", "filters": {"country": "Canada"}},
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()
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
