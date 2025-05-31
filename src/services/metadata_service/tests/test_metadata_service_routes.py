import pytest
from fastapi import status
import httpx

def test_health(client):
    res = client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    assert res.json() == {"status": "ok"}

def test_describe_asset(monkeypatch, client):
    asset_id = "123"
    dummy_bytes = b"fake-image-bytes"

    # Prepare two sequential GET responses: metadata list then file content
    class RMeta:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return [{"url": "http://assets.test/download/123", "content_type": "image/jpeg"}]

    class RFile:
        status_code = 200
        content = dummy_bytes
        def raise_for_status(self): pass

    responses = [RMeta(), RFile()]
    async def fake_get(self, url, **kwargs):
        return responses.pop(0)
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    # Mock call to LLM Orchestration
    async def fake_post(self, url, **kwargs):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"description": "an image"}
        return R()
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    res = client.post(f"/describe/{asset_id}")
    assert res.status_code == status.HTTP_200_OK
    body = res.json()
    assert body["asset_id"] == asset_id
    assert body["description"] == "an image"