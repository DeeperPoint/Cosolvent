import pytest
from fastapi import status
import httpx

def test_health_ok(monkeypatch, client):
    # Mock downstream health check
    class DummyResp:
        status_code = 200
        content = b"OK"
        headers = {"content-type": "text/plain"}

    async def fake_send(req, **kwargs):
        return DummyResp()

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)

    res = client.get("/api/assets/health")
    assert res.status_code == 200
    assert res.text == "OK"

def test_cors_headers_present(monkeypatch, client):
    # reuse health mock
    class DummyResp:
        status_code = 200
        content = b"OK"
        headers = {"content-type": "text/plain"}

    async def fake_send(req, **kwargs):
        return DummyResp()

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)

    res = client.options("/api/assets/anypath")
    assert res.headers.get("access-control-allow-origin") == "*"
    assert "GET" in res.headers.get("access-control-allow-methods", "")

def test_unknown_service_returns_404(client):
    res = client.get("/api/unknown/service")
    assert res.status_code == status.HTTP_404_NOT_FOUND