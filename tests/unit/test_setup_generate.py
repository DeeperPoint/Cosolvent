from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from app.setup_app import create_setup_app

FIXTURES = Path(__file__).resolve().parents[1] / "test_config"


def test_setup_generate_and_check_sync(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = yaml.safe_load((FIXTURES / "minimal.yaml").read_text(encoding="utf-8"))
    (tmp_path / "marketplace.yaml").write_text(
        (FIXTURES / "minimal.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    app = create_setup_app()
    client = TestClient(app)

    generate = client.post(
        "/api/setup/generate",
        json={
            "config": cfg,
            "mode": "mvp",
            "export_enabled": False,
            "overwrite_policy": "managed",
        },
    )
    assert generate.status_code == 200, generate.text
    body = generate.json()
    assert body["ok"] is True
    assert "app/generated/role_alias_router.py" in body["generated_files"]

    check = client.post(
        "/api/setup/generate/check",
        json={"config": cfg, "mode": "mvp", "overwrite_policy": "managed"},
    )
    assert check.status_code == 200, check.text
    check_body = check.json()
    assert check_body["in_sync"] is True
