"""Parse `POST .../register` as JSON or multipart (email + fields JSON + files)."""

from __future__ import annotations

import json

from fastapi import Request, UploadFile

from app.core.config import settings
from app.core.exceptions import AppError

MAX_REGISTER_UPLOAD_FILES = 10
# Total bytes a single registration submission may carry across all uploaded
# files. Per-file limit (``settings.files_max_upload_bytes``) still applies;
# this is the *aggregate* cap so a producer can't upload e.g. ten 9 MB images.
MAX_REGISTER_UPLOAD_TOTAL_BYTES = 10 * 1024 * 1024  # 10 MB


async def _extract_file_parts_from_form(form) -> list[tuple[str, str, str, bytes]]:
    """Collect uploaded bytes from multipart form.

    Returns ``(field_name, filename, content_type, data)`` tuples. ``field_name``
    is the multipart key the client used; for the generic ``files`` / ``file``
    keys it stays as-is so callers can fall back to a default category.
    Deduplicate by ``UploadFile`` object id.
    """
    file_parts: list[tuple[str, str, str, bytes]] = []
    seen_ids: set[int] = set()

    async def consume(field_name: str, item: object) -> None:
        # Starlette/FastAPI can surface file parts as different UploadFile classes.
        # Accept either explicit UploadFile instances or duck-typed upload objects.
        is_upload = isinstance(item, UploadFile) or (
            hasattr(item, "read") and hasattr(item, "filename") and hasattr(item, "content_type")
        )
        if not is_upload:
            return
        oid = id(item)
        if oid in seen_ids:
            return
        seen_ids.add(oid)
        data = await item.read()
        if not data:
            return
        raw_name = getattr(item, "filename", None)
        filename = (raw_name or "").strip() or "upload"
        if len(data) > settings.files_max_upload_bytes:
            raise AppError("File exceeds upload size limit", status_code=413)
        file_parts.append(
            (
                field_name,
                filename,
                item.content_type or "application/octet-stream",
                data,
            )
        )

    # Walk every form key once so files appended under schema field names
    # (e.g. ``certification_documents``, ``farm_photos``) keep their source
    # tag. The generic ``files``/``file`` keys remain supported for older
    # clients — they just won't carry a per-field category.
    for key in form.keys():
        if key in ("email", "fields"):
            continue
        for item in form.getlist(key):
            await consume(key, item)

    return file_parts


async def parse_authenticated_register_body(request: Request) -> dict | None:
    """Session cookie present: expect JSON ``{ \"fields\": { ... } }``."""
    raw = await request.body()
    if not raw.strip():
        return None
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError("Invalid JSON body", status_code=422) from exc
    if not isinstance(body, dict):
        return None
    return body.get("fields")


async def parse_anonymous_register(
    request: Request,
) -> tuple[str | None, dict | None, list[tuple[str, str, str, bytes]]]:
    """
    No session: JSON **or** multipart/form-data.

    Multipart form fields:
    - ``email`` (string)
    - ``fields`` (string containing JSON object)
    - ``files`` or ``file`` — one or more file parts
    """
    ct = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in ct:
        form = await request.form()
        raw_email = form.get("email")
        email = raw_email.strip() if isinstance(raw_email, str) else None

        raw_fields = form.get("fields")
        fields: dict | None = None
        if isinstance(raw_fields, str):
            try:
                parsed = json.loads(raw_fields)
            except json.JSONDecodeError as exc:
                raise AppError('Invalid JSON in form field "fields"', status_code=422) from exc
            fields = parsed if isinstance(parsed, dict) else None

        file_parts = await _extract_file_parts_from_form(form)

        if len(file_parts) > MAX_REGISTER_UPLOAD_FILES:
            raise AppError(
                f"At most {MAX_REGISTER_UPLOAD_FILES} files may be attached",
                status_code=422,
            )
        return email, fields, file_parts

    if "application/json" in ct:
        raw = await request.body()
        if not raw.strip():
            return None, None, []
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AppError("Invalid JSON body", status_code=422) from exc
        if not isinstance(body, dict):
            return None, None, []
        email_raw = body.get("email")
        email = str(email_raw).strip() if email_raw else None
        fields = body.get("fields")
        if fields is not None and not isinstance(fields, dict):
            raise AppError('"fields" must be an object', status_code=422)
        return email, fields, []

    raise AppError(
        "Content-Type must be application/json or multipart/form-data",
        status_code=415,
    )
