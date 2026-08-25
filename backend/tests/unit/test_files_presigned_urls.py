"""Presigned URL signing (S3 storage).

SigV2 is deprecated by AWS and rejected outright by MinIO, Cloudflare R2, Wasabi
and Ceph. Against real AWS botocore negotiates SigV4 on its own, so an unpinned
signature version works in production and fails only against a custom endpoint —
including the MinIO in this repo's docker-compose. Pinning it is what keeps those
two environments behaving the same.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import settings
from app.modules.files import storage


@pytest.fixture
def minio_endpoint(monkeypatch):
    """Point storage at a custom endpoint — the case that exposed the fallback."""
    monkeypatch.setattr(settings, "s3_endpoint_url", "http://localhost:19000")
    monkeypatch.setattr(settings, "s3_bucket", "cosolvent-files")
    monkeypatch.setattr(settings, "s3_region", "us-east-1")
    monkeypatch.setattr(settings, "aws_access_key_id", "minioadmin")
    monkeypatch.setattr(settings, "aws_secret_access_key", "minioadmin")


def test_client_pins_sigv4(minio_endpoint):
    client = storage._get_client()
    assert client.meta.config.signature_version == "s3v4"


def test_presigned_url_uses_sigv4_parameters(minio_endpoint):
    """SigV4 signs into `X-Amz-*`; SigV2 emits AWSAccessKeyId/Signature/Expires."""
    url = storage._generate_presigned_get_url("uploads/abc/report.pdf", 900)
    params = parse_qs(urlparse(url).query)

    assert "X-Amz-Algorithm" in params
    assert "X-Amz-Signature" in params
    assert "X-Amz-Credential" in params

    # The SigV2 shape must be gone entirely.
    assert "AWSAccessKeyId" not in params
    assert "Signature" not in params


def test_presigned_url_targets_the_requested_object(minio_endpoint):
    url = storage._generate_presigned_get_url("uploads/abc/report.pdf", 900)
    parsed = urlparse(url)
    assert parsed.netloc == "localhost:19000"
    assert "uploads/abc/report.pdf" in parsed.path


def test_sigv4_holds_without_a_custom_endpoint(monkeypatch):
    """Real-AWS path: already SigV4 by negotiation, but pinning must not break it."""
    monkeypatch.setattr(settings, "s3_endpoint_url", None)
    monkeypatch.setattr(settings, "s3_region", "eu-west-1")
    monkeypatch.setattr(settings, "aws_access_key_id", "AKIAEXAMPLE")
    monkeypatch.setattr(settings, "aws_secret_access_key", "secret")

    client = storage._get_client()
    assert client.meta.config.signature_version == "s3v4"
