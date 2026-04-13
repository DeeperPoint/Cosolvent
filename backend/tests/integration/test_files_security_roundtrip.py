from __future__ import annotations

import pytest

from tests.e2e.helpers import get_base_url, new_client, random_email, require_mode, signup_user

USER_PASSWORD = "UserPass123!"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_private_upload_permissions_and_signed_urls():
    require_mode("RUN_INTEGRATION")
    base_url = get_base_url("INTEGRATION_BASE_URL")
    producer = new_client(base_url)
    buyer = new_client(base_url)

    try:
        await signup_user(
            producer,
            email=random_email("producer-files"),
            password=USER_PASSWORD,
            participant_type="producer",
        )
        producer_register = await producer.post("/api/profiles/producer/register")
        producer_register.raise_for_status()
        producer_draft_id = producer_register.json()["id"]

        producer_upload = await producer.post(
            "/api/files/upload",
            data={"privacy": "private", "category": "onboarding", "profile_id": producer_draft_id},
            files={"file": ("onboarding.txt", b"private-doc", "text/plain")},
        )
        producer_upload.raise_for_status()
        producer_file = producer_upload.json()
        assert producer_file["privacy"] == "private"
        assert "X-Amz-" in producer_file["url"]

        producer_get = await producer.get(f"/api/files/{producer_file['id']}")
        producer_get.raise_for_status()
        assert "X-Amz-" in producer_get.json()["url"]

        await signup_user(
            buyer,
            email=random_email("buyer-files"),
            password=USER_PASSWORD,
            participant_type="buyer",
        )
        buyer_register = await buyer.post("/api/profiles/buyer/register")
        buyer_register.raise_for_status()
        buyer_draft_id = buyer_register.json()["id"]

        forbidden_private_upload = await buyer.post(
            "/api/files/upload",
            data={"privacy": "private", "category": "onboarding", "profile_id": buyer_draft_id},
            files={"file": ("onboarding.txt", b"private-doc", "text/plain")},
        )
        assert forbidden_private_upload.status_code == 403

        invalid_privacy_upload = await buyer.post(
            "/api/files/upload",
            data={"privacy": "secret", "category": "onboarding", "profile_id": buyer_draft_id},
            files={"file": ("onboarding.txt", b"private-doc", "text/plain")},
        )
        assert invalid_privacy_upload.status_code == 422
    finally:
        await producer.aclose()
        await buyer.aclose()
