from __future__ import annotations

import pytest

from tests.e2e.helpers import get_base_url, new_client, random_email, require_mode, signup_user

USER_PASSWORD = "UserPass123!"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_profile_draft_returns_422_not_500():
    require_mode("RUN_INTEGRATION")
    base_url = get_base_url("INTEGRATION_BASE_URL")
    client = new_client(base_url)
    try:
        await signup_user(
            client,
            email=random_email("invalid-draft"),
            password=USER_PASSWORD,
            participant_type="buyer",
        )

        register = await client.post("/api/profiles/buyer/register")
        register.raise_for_status()

        # Intentionally missing required schema fields.
        draft = await client.put("/api/profiles/buyer/draft", json={"fields": {"org_name": "Legacy Name"}})
        assert draft.status_code == 422
        assert "invalid" in str(draft.json().get("detail", "")).lower()
    finally:
        await client.aclose()
