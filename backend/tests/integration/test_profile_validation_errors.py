from __future__ import annotations

import pytest

from tests.e2e.helpers import get_base_url, new_client, random_email, require_mode, signup_user

USER_PASSWORD = "UserPass123!"

# Payloads that are malformed for *any* marketplace schema, so this suite asserts the
# HTTP contract rather than one vertical's field list.
#
# The earlier version sent `{"org_name": "Legacy Name"}` and expected 422 on the grounds
# that required fields were missing. Whether that holds depends entirely on which config
# is loaded — under `agriculture.yaml` `org_name` is the only required buyer field, so the
# payload is valid and the request correctly returns 200. Since `marketplace.yaml` is
# gitignored and chosen per machine, that made the result depend on local setup.
MALFORMED_DRAFTS = [
    pytest.param({"fields": "not-a-mapping"}, id="fields-is-a-string"),
    pytest.param({"fields": ["a", "b"]}, id="fields-is-a-list"),
    pytest.param({"fields": 123}, id="fields-is-a-number"),
]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("payload", MALFORMED_DRAFTS)
async def test_invalid_profile_draft_returns_422_not_500(payload):
    """A malformed draft must fail validation cleanly.

    The regression guarded against is a 500: an unhandled error from the schema
    validator leaking as a server fault rather than being reported to the caller.
    """
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

        draft = await client.put("/api/profiles/buyer/draft", json=payload)

        assert draft.status_code == 422, f"expected 422, got {draft.status_code}: {draft.text[:200]}"
        assert draft.status_code != 500
        # A validation failure must say something the caller can act on.
        assert draft.json().get("detail")
    finally:
        await client.aclose()
