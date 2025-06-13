# Ensure metadata_service/src is on PYTHONPATH
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import pytest
import httpx

from core.asset_client import update_metadata
from schemas.asset import AssetUpdatePayload

class DummyResponse:
    def __init__(self, status_code):
        self.status_code = status_code
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("Error status", request=None, response=self)

class DummyClientSuccess:
    def __init__(self, *args, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    async def patch(self, url, json):
        return DummyResponse(status_code=200)

class DummyClientError(DummyClientSuccess):
    async def patch(self, url, json):
        return DummyResponse(status_code=500)

@pytest.mark.asyncio
async def test_update_metadata_success(monkeypatch):
    monkeypatch.setattr(httpx, 'AsyncClient', DummyClientSuccess)
    payload = AssetUpdatePayload(asset_id="1234", description="desc", status="described")
    # Should not raise any exceptions
    await update_metadata(payload)

@pytest.mark.asyncio
async def test_update_metadata_http_error(monkeypatch):
    monkeypatch.setattr(httpx, 'AsyncClient', DummyClientError)
    payload = AssetUpdatePayload(asset_id="1234", description="desc", status="described")
    with pytest.raises(httpx.HTTPStatusError):
        await update_metadata(payload)
