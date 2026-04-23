"""E2E: /api/setup/... endpoints.

The setup endpoints are how the onboarding wizard reads + writes
``marketplace.yaml`` and drives code generation.  They are public
(no auth required) but destructive operations (``save``, ``generate``)
should respect validation errors and stay inside the project tree.
"""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_onboarding_panel_returns_html(
    anonymous_client: httpx.AsyncClient,
) -> None:
    r = await anonymous_client.get("/onboarding")
    assert r.status_code == 200
    assert "html" in (r.headers.get("content-type", "").lower())


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_config_template_returns_config_and_source_path(
    anonymous_client: httpx.AsyncClient,
) -> None:
    r = await anonymous_client.get("/api/setup/config-template")
    assert r.status_code == 200
    body = r.json()
    assert "config" in body
    assert "source_path" in body
    assert "runtime_path" in body


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_presets_returns_list(
    anonymous_client: httpx.AsyncClient,
) -> None:
    r = await anonymous_client.get("/api/setup/presets")
    assert r.status_code == 200
    assert isinstance(r.json().get("presets"), list)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_validate_accepts_valid_config(
    anonymous_client: httpx.AsyncClient,
) -> None:
    # Round-trip: read template, then re-submit it through /validate.
    template = await anonymous_client.get("/api/setup/config-template")
    config = template.json()["config"]

    r = await anonymous_client.post("/api/setup/validate", json={"config": config})
    assert r.status_code == 200
    assert r.json().get("valid") is True


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_validate_rejects_invalid_config(
    anonymous_client: httpx.AsyncClient,
) -> None:
    r = await anonymous_client.post(
        "/api/setup/validate",
        json={"config": {"marketplace": {"name": ""}}},
    )
    assert r.status_code in (400, 422)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_render_yaml_produces_yaml_string(
    anonymous_client: httpx.AsyncClient,
) -> None:
    template = await anonymous_client.get("/api/setup/config-template")
    config = template.json()["config"]

    r = await anonymous_client.post(
        "/api/setup/render-yaml", json={"config": config}
    )
    assert r.status_code == 200
    yaml_text = r.json().get("yaml")
    assert isinstance(yaml_text, str)
    assert "marketplace" in yaml_text


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_save_rejects_path_outside_project(
    anonymous_client: httpx.AsyncClient,
) -> None:
    template = await anonymous_client.get("/api/setup/config-template")
    config = template.json()["config"]
    r = await anonymous_client.post(
        "/api/setup/save",
        json={
            "config": config,
            "output_path": "/tmp/hacker.yaml",
            "apply_runtime": False,
        },
    )
    assert r.status_code in (400, 403)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_save_rejects_non_yaml_extension(
    anonymous_client: httpx.AsyncClient,
) -> None:
    template = await anonymous_client.get("/api/setup/config-template")
    config = template.json()["config"]
    r = await anonymous_client.post(
        "/api/setup/save",
        json={"config": config, "output_path": "output.json", "apply_runtime": False},
    )
    assert r.status_code == 400


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_generate_check_returns_summary(
    anonymous_client: httpx.AsyncClient,
) -> None:
    r = await anonymous_client.post("/api/setup/generate/check", json={})
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_assets_rejects_unknown_names(
    anonymous_client: httpx.AsyncClient,
) -> None:
    r = await anonymous_client.get("/api/setup/assets/does-not-exist.js")
    assert r.status_code == 404


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_assets_serves_known_file(
    anonymous_client: httpx.AsyncClient,
) -> None:
    r = await anonymous_client.get("/api/setup/assets/main.js")
    assert r.status_code == 200
    assert "javascript" in r.headers.get("content-type", "").lower()
