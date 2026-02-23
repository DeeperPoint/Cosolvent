"""Document processing to structured field extraction."""

from __future__ import annotations

import json

from app.core.exceptions import ServiceUnavailableError
from app.modules.ai.llm_client import generate


async def extract_fields_from_document(
    document_text: str,
    participant_type: str,
    field_definitions: list[dict],
) -> dict:
    """Extract profile fields from document text using AI."""
    allowed_fields = []
    for field in field_definitions:
        allowed_fields.append(
            {
                "name": field.get("name"),
                "type": field.get("type"),
                "options": field.get("options"),
            }
        )

    prompt = (
        f"Participant type: {participant_type}\n"
        f"Allowed fields: {json.dumps(allowed_fields, ensure_ascii=True)}\n"
        "Extract values from the document text and return valid JSON object only. "
        "Only include known field names, omit unknowns.\n\n"
        f"Document text:\n{document_text}"
    )
    raw = await generate(
        [
            {"role": "system", "content": "You extract structured data and return JSON only."},
            {"role": "user", "content": prompt},
        ],
        use_case="document_extraction",
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ServiceUnavailableError("AI extraction returned non-JSON response") from exc
    if not isinstance(parsed, dict):
        raise ServiceUnavailableError("AI extraction returned invalid object")
    return parsed
