"""S3 storage abstraction."""

from __future__ import annotations

import uuid

import boto3

from app.core.config import settings


def _get_client():
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


async def upload_file(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Upload file to S3, return the URL."""
    key = f"uploads/{uuid.uuid4().hex}/{filename}"
    client = _get_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{key}"


async def delete_file(url: str) -> None:
    """Delete file from S3 by URL."""
    # Extract key from URL
    prefix = f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/"
    if url.startswith(prefix):
        key = url[len(prefix):]
        client = _get_client()
        client.delete_object(Bucket=settings.s3_bucket, Key=key)
