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
from botocore.config import Config as BotoConfig

from app.core.config import settings

logger = logging.getLogger("cosolvent")
_UPLOAD_PREFIX = "uploads/"
_MAX_FILENAME_LENGTH = 128


@dataclass(frozen=True)
class UploadedObject:
    key: str
    url: str


def _get_client():
    kwargs = {
        "service_name": "s3",
        "region_name": settings.s3_region,
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
        # Pin SigV4. Against real AWS botocore negotiates it anyway, but against a
        # custom endpoint it falls back to SigV2 — which AWS has deprecated and
        # which MinIO, R2, Wasabi and Ceph reject outright. Without this, presigned
        # URLs work in production and silently break on any non-AWS store,
        # including the MinIO in this repo's own docker-compose.
        "config": BotoConfig(signature_version="s3v4"),
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
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


def public_url_for_key(key: str) -> str:
    if settings.s3_endpoint_url:
        # Handle local MinIO style URLs
        base = settings.s3_endpoint_url.rstrip("/")
        # In docker-compose, internal endpoint is http://s3:9000
        # Externally it might be http://localhost:19000
        # If the endpoint contains 'localhost' or '127.0.0.1' or the s3 service name, 
        # we might need to be smart, but for now let's just use the endpoint as provided.
        # Often for local dev we want the URL to be accessible by the browser (localhost).
        return f"{base}/{settings.s3_bucket}/{quote(key, safe='/')}"
    return f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{quote(key, safe='/')}"


def extract_upload_key_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if settings.s3_endpoint_url:
        endpoint_parsed = urlparse(settings.s3_endpoint_url)
        if parsed.netloc != endpoint_parsed.netloc:
            return None
        # URL is likely {endpoint}/{bucket}/{key}
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
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )


async def generate_presigned_get_url(key: str, expires_seconds: int) -> str:
    return await asyncio.to_thread(_generate_presigned_get_url, key, expires_seconds)
