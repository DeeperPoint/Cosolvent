"""S3 storage abstraction."""

from __future__ import annotations

import asyncio
import uuid
from io import BytesIO
from typing import BinaryIO

import boto3

from app.core.config import settings


def _get_client():
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


def _upload_object(file_obj: BinaryIO, key: str, content_type: str) -> None:
    client = _get_client()
    file_obj.seek(0)
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=file_obj,
        ContentType=content_type,
    )


async def upload_fileobj(file_obj: BinaryIO, filename: str, content_type: str) -> str:
    """Upload a file-like object to S3 and return the object URL."""
    key = f"uploads/{uuid.uuid4().hex}/{filename}"
    await asyncio.to_thread(_upload_object, file_obj, key, content_type)
    return f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{key}"


async def upload_file(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload bytes to S3, return the URL."""
    return await upload_fileobj(BytesIO(file_bytes), filename, content_type)


def _delete_object(key: str) -> None:
    client = _get_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=key)


async def delete_file(url: str) -> None:
    """Delete file from S3 by URL."""
    # Extract key from URL
    prefix = f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/"
    if url.startswith(prefix):
        key = url[len(prefix):]
        await asyncio.to_thread(_delete_object, key)
