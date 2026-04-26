"""S3 storage abstraction."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO
from urllib.parse import quote, unquote, urlparse

import boto3

from app.core.config import settings

logger = logging.getLogger("cosolvent")
_UPLOAD_PREFIX = "uploads/"
_MAX_FILENAME_LENGTH = 128


@dataclass(frozen=True)
class UploadedObject:
    key: str
    url: str


def _get_client():
    """Client for backend-side operations (uploads, deletes, listings).

    Uses the *internal* endpoint so backend ↔ MinIO traffic stays inside the
    docker network.
    """
    kwargs = {
        "service_name": "s3",
        "region_name": settings.s3_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client(**kwargs)


def _get_public_client():
    """Client for generating browser-facing URLs (e.g. presigned GETs).

    Points at ``S3_PUBLIC_URL`` (defaulting to ``S3_ENDPOINT_URL``) so the
    URLs it produces resolve from the user's browser, not from inside the
    container network. Credentials are the same; SigV4 signs the path +
    canonical headers, MinIO accepts the signature when the public host
    receives the request.
    """
    public_endpoint = settings.s3_public_url or settings.s3_endpoint_url
    kwargs = {
        "service_name": "s3",
        "region_name": settings.s3_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }
    if public_endpoint:
        kwargs["endpoint_url"] = public_endpoint
    return boto3.client(**kwargs)


def _sanitize_filename(filename: str) -> str:
    basename = filename.replace("\\", "/").split("/")[-1]
    basename = re.sub(r"[\x00-\x1f\x7f]+", "", basename)
    basename = re.sub(r"\s+", " ", basename).strip()
    basename = re.sub(r"[^A-Za-z0-9._ -]", "_", basename)
    basename = basename.strip(" .")
    if not basename:
        basename = "upload.bin"
    if len(basename) > _MAX_FILENAME_LENGTH:
        basename = basename[:_MAX_FILENAME_LENGTH]
    return basename


def is_safe_upload_key(key: str) -> bool:
    if not key or not key.startswith(_UPLOAD_PREFIX):
        return False
    parts = key.split("/")
    if any(part in {"", ".", ".."} for part in parts[1:]):
        return False
    return True


def _browser_facing_endpoint() -> str | None:
    """Resolve the URL the browser should use to reach the S3-compatible store.

    Prefers ``S3_PUBLIC_URL`` (e.g. ``http://localhost:19000`` for docker-compose
    MinIO). Falls back to ``S3_ENDPOINT_URL`` for single-host setups where the
    backend and the browser see the same hostname.
    """
    public = settings.s3_public_url or settings.s3_endpoint_url
    return public.rstrip("/") if public else None


def public_url_for_key(key: str) -> str:
    base = _browser_facing_endpoint()
    if base:
        return f"{base}/{settings.s3_bucket}/{quote(key, safe='/')}"
    return f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{quote(key, safe='/')}"


def extract_upload_key_from_url(url: str) -> str | None:
    """Reverse of ``public_url_for_key`` — accepts either the internal or
    public endpoint, so URLs stored in the DB before ``S3_PUBLIC_URL`` was
    introduced still parse cleanly during deletes/cleanup.
    """
    parsed = urlparse(url)
    accepted_hosts: set[str] = set()
    for endpoint in (settings.s3_endpoint_url, settings.s3_public_url):
        if endpoint:
            accepted_hosts.add(urlparse(endpoint).netloc)

    if accepted_hosts:
        if parsed.netloc not in accepted_hosts:
            return None
        path = parsed.path.lstrip("/")
        if not path.startswith(f"{settings.s3_bucket}/"):
            return None
        key = unquote(path[len(settings.s3_bucket) + 1 :])
    else:
        expected_host = f"{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com"
        if parsed.scheme != "https" or parsed.netloc != expected_host:
            return None
        key = unquote(parsed.path.lstrip("/"))

    if not is_safe_upload_key(key):
        return None
    return key


def _upload_object(file_obj: BinaryIO, key: str, content_type: str) -> UploadedObject:
    client = _get_client()
    file_obj.seek(0)
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=file_obj,
        ContentType=content_type,
    )
    return UploadedObject(key=key, url=public_url_for_key(key))


async def upload_fileobj(file_obj: BinaryIO, filename: str, content_type: str) -> UploadedObject:
    """Upload a file-like object to S3 and return the object URL."""
    safe_name = _sanitize_filename(filename)
    key = f"{_UPLOAD_PREFIX}{uuid.uuid4().hex}/{safe_name}"
    return await asyncio.to_thread(_upload_object, file_obj, key, content_type)


async def upload_file(file_bytes: bytes, filename: str, content_type: str) -> UploadedObject:
    """Upload bytes to S3, return the URL."""
    return await upload_fileobj(BytesIO(file_bytes), filename, content_type)


def _delete_object(key: str) -> None:
    client = _get_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=key)


async def delete_file(*, s3_key: str | None = None, url: str | None = None) -> None:
    """Delete file from S3 by key with URL fallback for legacy records."""
    key = s3_key if s3_key and is_safe_upload_key(s3_key) else None
    if key is None and url:
        key = extract_upload_key_from_url(url)
    if key is None:
        logger.warning("Skipping S3 delete due to missing or unsafe key")
        return
    await asyncio.to_thread(_delete_object, key)


def _generate_presigned_get_url(key: str, expires_seconds: int) -> str:
    # Sign against the browser-facing endpoint so the URL resolves from
    # the user's machine. Signing against ``s3:9000`` (internal docker
    # hostname) yields a presigned URL the browser cannot reach.
    client = _get_public_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )


async def generate_presigned_get_url(key: str, expires_seconds: int) -> str:
    return await asyncio.to_thread(_generate_presigned_get_url, key, expires_seconds)
