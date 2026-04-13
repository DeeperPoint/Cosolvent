from __future__ import annotations

import pytest

from tests.e2e.helpers import get_base_url, new_client, require_mode


@pytest.mark.integration
@pytest.mark.asyncio
async def test_setup_preset_endpoint_contract():
    require_mode("RUN_INTEGRATION")
    base_url = get_base_url("INTEGRATION_BASE_URL")
    client = new_client(base_url)
    try:
        response = await client.get("/api/setup/presets")
        response.raise_for_status()
        body = response.json()
        presets = body.get("presets")
        assert isinstance(presets, list)
        assert len(presets) >= 3
        first = presets[0]
        assert {"id", "title", "description", "when_to_use", "config"}.issubset(first.keys())
    finally:
        await client.aclose()
