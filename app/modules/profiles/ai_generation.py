"""AI profile content generation."""

from __future__ import annotations

import json

from app.modules.ai.llm_client import generate


async def generate_profile_content(
    fields: dict,
    participant_type: str,
    marketplace_context: str,
) -> str:
    """Generate AI-written profile content from raw field data."""
    fields_json = json.dumps(fields, indent=2, ensure_ascii=True, sort_keys=True)
    messages = [
        {
            "role": "system",
            "content": (
                "You are an assistant that writes concise, factual marketplace profile summaries. "
                "Do not invent facts. Use only provided fields. Keep it under 220 words."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Marketplace context: {marketplace_context}\n"
                f"Participant type: {participant_type}\n"
                f"Raw fields:\n{fields_json}\n\n"
                "Write a polished profile summary suitable for marketplace discovery."
            ),
        },
    ]
    return (await generate(messages, use_case="profile_generation")).strip()
