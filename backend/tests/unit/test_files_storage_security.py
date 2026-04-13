from __future__ import annotations

from io import BytesIO
from unittest.mock import Mock

import pytest

from app.modules.files import storage


@pytest.mark.asyncio
async def test_upload_fileobj_sanitizes_filename(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, str] = {}

    def fake_upload(file_obj, key: str, content_type: str):
        captured["key"] = key
        return storage.UploadedObject(key=key, url=f"https://example.com/{key}")

    monkeypatch.setattr(storage, "_upload_object", fake_upload)

    uploaded = await storage.upload_fileobj(
        BytesIO(b"payload"),
        "../..\\unsafe\nname?.txt",
        "text/plain",
    )

    assert uploaded.key.startswith("uploads/")
    assert ".." not in uploaded.key
    assert "\n" not in uploaded.key
    assert "?" not in uploaded.key
    assert uploaded.key.endswith("unsafename_.txt")
    assert captured["key"] == uploaded.key


@pytest.mark.asyncio
async def test_delete_file_rejects_non_upload_prefix(monkeypatch: pytest.MonkeyPatch):
    called = {"delete": False}

    def fake_delete(key: str):
        called["delete"] = True

    monkeypatch.setattr(storage, "_delete_object", fake_delete)

    await storage.delete_file(s3_key="private/secret.txt")

    assert called["delete"] is False


@pytest.mark.asyncio
async def test_generate_presigned_get_url_uses_requested_ttl(monkeypatch: pytest.MonkeyPatch):
    fake_client = Mock()
    fake_client.generate_presigned_url.return_value = "https://signed.example.com/file"
    monkeypatch.setattr(storage, "_get_client", lambda: fake_client)

    signed_url = await storage.generate_presigned_get_url("uploads/abc/doc.txt", 123)

    assert signed_url == "https://signed.example.com/file"
    fake_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": storage.settings.s3_bucket, "Key": "uploads/abc/doc.txt"},
        ExpiresIn=123,
    )
