"""Agriculture marketplace preset."""

from __future__ import annotations

import yaml
from pathlib import Path


def get_preset() -> dict:
    """Return the agriculture marketplace preset config dict."""
    example = Path(__file__).parent.parent.parent / "marketplace.example.yaml"
    if example.exists():
        return yaml.safe_load(example.read_text())

    # Fallback inline
    return {
        "marketplace": {
            "name": "GrainPlaza",
            "description": "Connecting specialty grain producers with global buyers",
            "industry": "Specialty Agriculture",
        },
        "participant_types": [
            {
                "name": "Producer", "slug": "producer", "role": "supply",
                "permissions": {
                    "can_list": True, "can_search": False,
                    "can_initiate_conversation": False, "can_receive_conversation": True,
                    "can_share_private_assets": True, "requires_onboarding": True,
                    "requires_approval": True, "visible_in_search": True,
                },
            },
            {
                "name": "Buyer", "slug": "buyer", "role": "demand",
                "permissions": {
                    "can_list": False, "can_search": True,
                    "can_initiate_conversation": True, "can_receive_conversation": True,
                    "can_share_private_assets": False, "requires_onboarding": True,
                    "requires_approval": False, "visible_in_search": False,
                },
            },
        ],
        "profile_schemas": {
            "producer": {"sections": [{"name": "Basic Information", "fields": [
                {"name": "farm_name", "label": "Farm Name", "type": "text", "required": True, "visibility": "public", "searchable": True},
                {"name": "country", "label": "Country", "type": "select", "required": True, "options": ["Canada", "USA", "Brazil"], "visibility": "public", "searchable": True},
                {"name": "primary_crops", "label": "Primary Crops", "type": "multi_select", "required": True, "options": ["Wheat", "Barley", "Canola"], "visibility": "public", "searchable": True},
            ]}]},
            "buyer": {"sections": [{"name": "Organization", "fields": [
                {"name": "org_name", "label": "Organization Name", "type": "text", "required": True, "visibility": "public", "searchable": True},
            ]}]},
        },
        "onboarding": {
            "producer": {"requires_approval": True, "approval_type": "manual", "document_upload_required": True, "ai_extraction_enabled": True, "ai_profile_generation": True, "welcome_email_on_approval": True, "profile_completeness_threshold": 80},
            "buyer": {"requires_approval": False, "approval_type": "auto", "document_upload_required": False, "ai_extraction_enabled": False, "ai_profile_generation": False, "welcome_email_on_approval": True, "profile_completeness_threshold": 100},
        },
        "communication": {"conversation_rules": [{"initiator": "buyer", "receiver": "producer", "requires_approval": True}]},
        "discovery": {
            "searchable_types": ["producer"],
            "filter_fields": ["country", "primary_crops"],
            "result_visibility": {"anonymous": "public", "authenticated": "protected"},
            "ai": {"vector_search_enabled": True, "rag_query_enabled": True, "follow_up_suggestions": True},
        },
    }
