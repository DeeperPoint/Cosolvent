"""Professional services marketplace preset."""

from __future__ import annotations


def get_preset() -> dict:
    return {
        "marketplace": {
            "name": "ProConnect",
            "description": "Connecting businesses with professional service providers",
            "industry": "Professional Services",
        },
        "participant_types": [
            {
                "name": "Provider", "slug": "provider", "role": "supply",
                "permissions": {
                    "can_list": True, "can_search": False,
                    "can_initiate_conversation": False, "can_receive_conversation": True,
                    "can_share_private_assets": True, "requires_onboarding": True,
                    "requires_approval": True, "visible_in_search": True,
                },
            },
            {
                "name": "Client", "slug": "client", "role": "demand",
                "permissions": {
                    "can_list": False, "can_search": True,
                    "can_initiate_conversation": True, "can_receive_conversation": True,
                    "can_share_private_assets": False, "requires_onboarding": True,
                    "requires_approval": False, "visible_in_search": False,
                },
            },
        ],
        "profile_schemas": {
            "provider": {"sections": [
                {"name": "Company Info", "fields": [
                    {"name": "company_name", "label": "Company Name", "type": "text", "required": True, "visibility": "public", "searchable": True},
                    {"name": "services", "label": "Services Offered", "type": "multi_select", "required": True, "options": ["Consulting", "Development", "Design", "Marketing", "Legal", "Accounting", "HR"], "visibility": "public", "searchable": True},
                    {"name": "industry_focus", "label": "Industry Focus", "type": "multi_select", "required": False, "options": ["Technology", "Finance", "Healthcare", "Manufacturing", "Retail"], "visibility": "public", "searchable": True},
                    {"name": "description", "label": "Description", "type": "rich_text", "required": False, "visibility": "public", "searchable": True},
                    {"name": "team_size", "label": "Team Size", "type": "number", "required": False, "visibility": "protected", "searchable": True},
                    {"name": "hourly_rate", "label": "Hourly Rate Range", "type": "text", "required": False, "visibility": "protected", "searchable": False},
                ]},
            ]},
            "client": {"sections": [
                {"name": "Organization", "fields": [
                    {"name": "org_name", "label": "Organization Name", "type": "text", "required": True, "visibility": "public", "searchable": True},
                    {"name": "industry", "label": "Industry", "type": "select", "required": True, "options": ["Technology", "Finance", "Healthcare", "Manufacturing", "Retail", "Other"], "visibility": "public", "searchable": True},
                    {"name": "description", "label": "About", "type": "rich_text", "required": False, "visibility": "public", "searchable": True},
                ]},
            ]},
        },
        "onboarding": {
            "provider": {"requires_approval": True, "approval_type": "manual", "document_upload_required": False, "ai_extraction_enabled": False, "ai_profile_generation": True, "welcome_email_on_approval": True, "profile_completeness_threshold": 80},
            "client": {"requires_approval": False, "approval_type": "auto", "document_upload_required": False, "ai_extraction_enabled": False, "ai_profile_generation": False, "welcome_email_on_approval": True, "profile_completeness_threshold": 100},
        },
        "communication": {"conversation_rules": [
            {"initiator": "client", "receiver": "provider", "requires_approval": True},
        ]},
        "discovery": {
            "searchable_types": ["provider"],
            "filter_fields": ["services", "industry_focus"],
            "result_visibility": {"anonymous": "public", "authenticated": "protected"},
            "ai": {"vector_search_enabled": True, "rag_query_enabled": True, "follow_up_suggestions": True},
        },
    }
