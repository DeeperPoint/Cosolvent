"""Prompt template management."""

from __future__ import annotations

from app.core.marketplace_config import MarketplaceConfig
from app.modules.ai import repository as repo

DEFAULT_PROMPTS = {
    "rag_query": (
        "You are an AI assistant for {marketplace_name}, a {industry} marketplace.\n"
        "Answer the user's question based on the provided context.\n"
        "If you don't have enough information, say so.\n\n"
        "Context:\n{context}\n\n"
        "Question: {query}"
    ),
    "follow_up": (
        "Based on the conversation so far about {marketplace_name}, "
        "suggest 3 follow-up questions the user might want to ask. "
        "Return them as a JSON array of strings."
    ),
    "profile_generation": (
        "Generate a professional marketplace profile for a {participant_type} "
        "in {marketplace_name} ({industry}).\n"
        "Based on the following raw data:\n{raw_data}\n\n"
        "Write a compelling, concise profile description."
    ),
    "document_extraction": (
        "Extract structured profile information from this document for a "
        "{participant_type} in {marketplace_name}.\n"
        "Expected fields: {field_names}\n\n"
        "Document content:\n{document_content}\n\n"
        "Return a JSON object with extracted field values."
    ),
}


async def get_prompt_template(intent: str, config: MarketplaceConfig) -> str:
    """Get a prompt template by intent, falling back to defaults."""
    custom = await repo.get_prompt(intent)
    if custom:
        return custom["template"]
    return DEFAULT_PROMPTS.get(intent, "")


def format_prompt(template: str, config: MarketplaceConfig, **kwargs) -> str:
    """Format a prompt template with marketplace context and additional kwargs."""
    return template.format(
        marketplace_name=config.marketplace.name,
        industry=config.marketplace.industry,
        **kwargs,
    )
