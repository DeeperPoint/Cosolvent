from __future__ import annotations

from fastapi.testclient import TestClient

from app.setup_app import create_setup_app


def test_setup_presets_contract_and_order():
    app = create_setup_app()
    client = TestClient(app)

    response = client.get("/api/setup/presets")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "presets" in body
    presets = body["presets"]
    assert isinstance(presets, list)
    assert [p["id"] for p in presets] == [
        "agriculture_b2b",
        "services_b2b",
        "manufacturing_b2b",
    ]
    for preset in presets:
        assert preset["title"]
        assert preset["description"]
        assert preset["when_to_use"]
        assert isinstance(preset["config"], dict)


def test_setup_presets_configs_validate():
    app = create_setup_app()
    client = TestClient(app)
    presets = client.get("/api/setup/presets").json()["presets"]
    for preset in presets:
        resp = client.post("/api/setup/validate", json={"config": preset["config"]})
        assert resp.status_code == 200, f"{preset['id']} invalid: {resp.text}"
