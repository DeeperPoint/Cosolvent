"""Local E2E checks for onboarding UX surface."""

from __future__ import annotations

import os

import httpx
import pytest


def _require_e2e_env() -> None:
    if os.getenv("RUN_E2E") != "1":
        pytest.skip("RUN_E2E=1 required")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_onboarding_surface_is_guided_and_human_friendly():
    _require_e2e_env()
    base_url = os.getenv("E2E_BASE_URL", "http://localhost:18000").rstrip("/")
    async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
        page = await client.get("/onboarding")
        page.raise_for_status()
        html = page.text
        if 'id="introScene"' in html:
            assert "Build your marketplace" in html and "thin market" in html
            assert 'id="startSetupBtn"' in html
            assert 'id="wizardScene"' in html
            assert "Advanced JSON Editor" in html
            assert 'id="floatingGlossaryBtn"' in html
            assert 'id="openAdvancedDrawerBtn"' in html
            assert "Configure Marketplace Onboarding" not in html
            assert "requires_approval" not in html
            assert 'data-help-path="' in html
            assert 'class="help-dot"' in html
            assert 'id="helpPopover"' in html
            assert 'role="tooltip"' in html
        else:
            assert "Configure Marketplace Onboarding" in html
            pytest.skip("Onboarding v2 disabled in runtime configuration")

        presets = await client.get("/api/setup/presets")
        presets.raise_for_status()
        preset_body = presets.json()
        assert isinstance(preset_body.get("presets"), list)
        assert len(preset_body["presets"]) >= 3

        main_js = await client.get("/api/setup/assets/main.js")
        main_js.raise_for_status()
        assert "application/javascript" in main_js.headers.get("content-type", "")
        assert "startSetup" in main_js.text
        assert "setScene" in main_js.text
        assert "setAdvancedDrawerOpen" in main_js.text
        assert "showHelpPopover" in main_js.text
        assert "document.addEventListener(\"mouseover\"" in main_js.text
        assert "document.addEventListener(\"focusin\"" in main_js.text
