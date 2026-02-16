from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.dependencies import get_config, get_current_user
from app.core.marketplace_config import load_marketplace_config
from app.modules.files.router import router

FIXTURES = Path(__file__).parent.parent / "test_config"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/files")
    app.dependency_overrides[get_current_user] = lambda: {
        "_id": "u1",
        "participant_type": "producer",
        "role": "user",
    }
    app.dependency_overrides[get_config] = lambda: load_marketplace_config(FIXTURES / "agriculture.yaml")
    return TestClient(app)


def test_upload_rejects_invalid_privacy(client: TestClient):
    with patch(
        "app.modules.files.router.service.upload_file_stream",
        new=AsyncMock(return_value={"id": "f1"}),
    ) as upload_mock:
        response = client.post(
            "/api/files/upload",
            data={"privacy": "secret"},
            files={"file": ("onboarding.txt", b"doc", "text/plain")},
        )

    assert response.status_code == 422
    upload_mock.assert_not_awaited()


def test_upload_rejects_oversized_file(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.modules.files.router.settings.files_max_upload_bytes", 1)
    with patch(
        "app.modules.files.router.service.upload_file_stream",
        new=AsyncMock(return_value={"id": "f1"}),
    ) as upload_mock:
        response = client.post(
            "/api/files/upload",
            data={"privacy": "public"},
            files={"file": ("onboarding.txt", b"too-large", "text/plain")},
        )

    assert response.status_code == 413
    upload_mock.assert_not_awaited()
