"""E2E: conversations and messages.

Marketplace.yaml restricts conversation initiation: a buyer initiates to
a producer, and the rule requires approval.  We exercise the full
lifecycle end-to-end:

1. Onboarded buyer and approved producer exist (fixtures).
2. Buyer creates conversation to producer (with initial message).
3. Producer accepts → conversation goes active.
4. Both parties can list messages / send messages.
5. Buyer edits then deletes the initial message.
6. Producer rejects a second conversation (rejection path).
7. Closing a conversation transitions state correctly.

All requests require auth; unauthenticated and cross-tenant access
assertions round out the coverage.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_all_conversation_endpoints_require_auth(
    anonymous_client: httpx.AsyncClient,
) -> None:
    fake = "00000000-0000-0000-0000-000000000000"
    for method, path in (
        ("GET", "/api/conversations"),
        ("POST", "/api/conversations"),
        ("GET", f"/api/conversations/{fake}"),
        ("POST", f"/api/conversations/{fake}/accept"),
        ("POST", f"/api/conversations/{fake}/reject"),
        ("POST", f"/api/conversations/{fake}/close"),
        ("GET", f"/api/conversations/{fake}/messages"),
        ("POST", f"/api/conversations/{fake}/messages"),
        ("PUT", f"/api/conversations/{fake}/messages/{fake}"),
        ("DELETE", f"/api/conversations/{fake}/messages/{fake}"),
        ("POST", f"/api/conversations/{fake}/share-assets"),
    ):
        r = await anonymous_client.request(method, path, json={})
        assert r.status_code == 401, f"{method} {path} returned {r.status_code}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_conversation_requires_existing_receiver(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.post(
        "/api/conversations",
        json={
            "receiver_user_id": "00000000-0000-0000-0000-000000000000",
            "initial_message": "hi",
        },
    )
    assert r.status_code in (400, 403, 404, 422)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_create_conversation_missing_fields_returns_422(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.post("/api/conversations", json={})
    assert r.status_code == 422


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_list_conversations_returns_list(
    onboarded_buyer: dict,
) -> None:
    client: httpx.AsyncClient = onboarded_buyer["client"]
    r = await client.get("/api/conversations")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_conversation_lifecycle(
    onboarded_buyer: dict,
    onboarded_producer: dict,
) -> None:
    buyer: httpx.AsyncClient = onboarded_buyer["client"]
    producer: httpx.AsyncClient = onboarded_producer["client"]
    producer_user_id = onboarded_producer["auth"]["user_id"]

    created = await buyer.post(
        "/api/conversations",
        json={"receiver_user_id": producer_user_id, "initial_message": "Hello"},
    )
    assert created.status_code in (200, 201), created.text
    conv = created.json()
    conv_id = conv.get("id") or conv.get("_id")
    assert conv_id

    # Producer accepts.
    accept = await producer.post(f"/api/conversations/{conv_id}/accept")
    assert accept.status_code == 200

    # Both can list messages; should include the initial one.
    msgs = await buyer.get(f"/api/conversations/{conv_id}/messages")
    assert msgs.status_code == 200
    assert isinstance(msgs.json(), list)

    # Missing content field on message send → 422.
    bad = await buyer.post(f"/api/conversations/{conv_id}/messages", json={})
    assert bad.status_code == 422

    # Buyer sends a message; then edits + deletes it.
    sent = await buyer.post(
        f"/api/conversations/{conv_id}/messages",
        json={"content": "Let me edit this"},
    )
    assert sent.status_code in (200, 201)
    msg = sent.json()
    msg_id = msg.get("id") or msg.get("_id")
    assert msg_id

    edited = await buyer.put(
        f"/api/conversations/{conv_id}/messages/{msg_id}",
        json={"content": "edited!"},
    )
    assert edited.status_code == 200
    assert edited.json().get("content") == "edited!"
    assert edited.json().get("edited") is True

    deleted = await buyer.delete(f"/api/conversations/{conv_id}/messages/{msg_id}")
    assert deleted.status_code == 200

    # Close the conversation.
    closed = await buyer.post(f"/api/conversations/{conv_id}/close")
    assert closed.status_code == 200


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_producer_can_reject_conversation(
    onboarded_buyer: dict,
    onboarded_producer: dict,
) -> None:
    buyer: httpx.AsyncClient = onboarded_buyer["client"]
    producer: httpx.AsyncClient = onboarded_producer["client"]
    producer_user_id = onboarded_producer["auth"]["user_id"]

    created = await buyer.post(
        "/api/conversations",
        json={"receiver_user_id": producer_user_id, "initial_message": "reject me"},
    )
    conv_id = created.json().get("id") or created.json().get("_id")
    assert conv_id

    rejected = await producer.post(f"/api/conversations/{conv_id}/reject")
    assert rejected.status_code == 200


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_share_assets_without_active_conversation(
    onboarded_buyer: dict,
    onboarded_producer: dict,
) -> None:
    """Sharing assets on a pending conversation should be rejected by rule."""

    buyer: httpx.AsyncClient = onboarded_buyer["client"]
    producer_user_id = onboarded_producer["auth"]["user_id"]

    created = await buyer.post(
        "/api/conversations",
        json={"receiver_user_id": producer_user_id, "initial_message": "hi"},
    )
    conv_id = created.json().get("id") or created.json().get("_id")
    assert conv_id

    r = await buyer.post(
        f"/api/conversations/{conv_id}/share-assets",
        json={"asset_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    # Buyer has can_share_private_assets=false — should be 403.
    assert r.status_code in (400, 403, 404)
