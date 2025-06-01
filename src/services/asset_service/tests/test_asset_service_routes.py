import pytest
from fastapi import status
from fastapi.testclient import TestClient

from services.asset_service.src.main import app
from services.asset_service.src.database.crud.asset_service_crud import AssetCRUD

@pytest.fixture
def client():
    return TestClient(app)

VALID_ASSET = {
    "id": "123",
    "user_id": "u1",
    "filename": "f.jpg",
    "content_type": "image/jpeg",
    "file_type": "image",
    "url": "http://s3/bucket/f.jpg"
}

async def fake_get_by_id(asset_id):
    return VALID_ASSET

@pytest.mark.asyncio
async def test_get_asset_by_id(monkeypatch, client):
    monkeypatch.setattr(AssetCRUD, "get_by_id", fake_get_by_id)
    response = client.get(f"/assets?asset_id={VALID_ASSET['id']}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert data[0] == VALID_ASSET

@pytest.mark.asyncio
async def test_get_asset_invalid_id_format(client):
    response = client.get("/assets?asset_id=invalid-id")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

