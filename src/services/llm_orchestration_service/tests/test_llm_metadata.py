import pytest
from fastapi import status
from fastapi.testclient import TestClient
import io

from services.llm_orchestration_service.src.main import app
from services.llm_orchestration_service.src.services.metadata_extraction import extract_textual_metadata_from_file
from services.llm_orchestration_service.src.services.metadata_extraction import image_to_text

# Override the extract_textual_metadata to a simple stub
@pytest.fixture(autouse=True)
def stub_extract(monkeypatch):
    async def fake_extract(file, service_name):
        return "stub description"
    monkeypatch.setattr(
        'services.llm_orchestration_service.src.services.metadata_extraction.extract_textual_metadata_from_file',
        fake_extract
    )

@pytest.mark.asyncio
async def test_llm_metadata_endpoint(client):
    # Build a dummy upload file
    file_content = b"dummy"
    file = io.BytesIO(file_content)
    # TestClient uses starlette.datastructures.UploadFile via form
    response = client.post(
        "/llm/metadata",
        files={"file": ("test.jpg", file, "image/jpeg")}
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert "result" in body
    assert body["result"]["description"] == "stub description"
