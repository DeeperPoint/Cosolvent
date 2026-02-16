from __future__ import annotations

from copy import deepcopy
from typing import Any


def _base_template(name: str, description: str, industry: str) -> dict[str, Any]:
    return {
        "marketplace": {
            "name": name,
            "description": description,
            "industry": industry,
        },
        "participant_types": [
            {
                "name": "Provider",
                "slug": "provider",
                "role": "supply",
                "permissions": {
                    "can_list": True,
                    "can_search": False,
                    "can_initiate_conversation": False,
                    "can_receive_conversation": True,
                    "can_share_private_assets": True,
                    "requires_onboarding": True,
                    "requires_approval": True,
                    "visible_in_search": True,
                },
            },
            {
                "name": "Client",
                "slug": "client",
                "role": "demand",
                "permissions": {
                    "can_list": False,
                    "can_search": True,
                    "can_initiate_conversation": True,
                    "can_receive_conversation": True,
                    "can_share_private_assets": False,
                    "requires_onboarding": True,
                    "requires_approval": False,
                    "visible_in_search": False,
                },
            },
        ],
        "profile_schemas": {
            "provider": {
                "sections": [
                    {
                        "name": "Public Profile",
                        "fields": [
                            {
                                "name": "company_name",
                                "label": "Company Name",
                                "type": "text",
                                "required": True,
                                "options": None,
                                "visibility": "public",
                                "searchable": True,
                            },
                            {
                                "name": "country",
                                "label": "Country",
                                "type": "text",
                                "required": True,
                                "options": None,
                                "visibility": "public",
                                "searchable": True,
                            },
                            {
                                "name": "specialties",
                                "label": "Specialties",
                                "type": "multi_select",
                                "required": False,
                                "options": ["General"],
                                "visibility": "public",
                                "searchable": True,
                            },
                        ],
                    }
                ]
            },
            "client": {
                "sections": [
                    {
                        "name": "Organization",
                        "fields": [
                            {
                                "name": "organization_name",
                                "label": "Organization Name",
                                "type": "text",
                                "required": True,
                                "options": None,
                                "visibility": "public",
                                "searchable": True,
                            },
                            {
                                "name": "country",
                                "label": "Country",
                                "type": "text",
                                "required": True,
                                "options": None,
                                "visibility": "public",
                                "searchable": True,
                            },
                        ],
                    }
                ]
            },
        },
        "onboarding": {
            "provider": {
                "requires_approval": True,
                "approval_type": "manual",
                "document_upload_required": True,
                "ai_extraction_enabled": False,
                "ai_profile_generation": False,
                "welcome_email_on_approval": True,
                "profile_completeness_threshold": 85,
            },
            "client": {
                "requires_approval": False,
                "approval_type": "auto",
                "document_upload_required": False,
                "ai_extraction_enabled": False,
                "ai_profile_generation": False,
                "welcome_email_on_approval": True,
                "profile_completeness_threshold": 100,
            },
        },
        "communication": {
            "conversation_rules": [
                {
                    "initiator": "client",
                    "receiver": "provider",
                    "requires_approval": True,
                }
            ]
        },
        "discovery": {
            "searchable_types": ["provider"],
            "filter_fields": ["country", "specialties"],
            "result_visibility": {"anonymous": "public", "authenticated": "protected"},
            "access": {
                "anonymous_search_enabled": False,
                "anonymous_filter_mode": "public_only",
            },
            "ai": {
                "vector_search_enabled": True,
                "rag_query_enabled": True,
                "follow_up_suggestions": True,
                "profile_retrieval_mode": "rag_strict",
                "rag_failure_behavior": "service_unavailable",
                "profile_similarity_threshold": 0.25,
                "max_vector_candidates": 500,
            },
        },
    }


def list_presets() -> list[dict[str, Any]]:
    b2b_services = _base_template(
        "ServiceHub",
        "Connect vetted service providers with business buyers.",
        "Professional Services",
    )
    b2b_services["participant_types"][0]["name"] = "Service Provider"
    b2b_services["profile_schemas"]["provider"]["sections"][0]["fields"][2]["options"] = [
        "Accounting",
        "Legal",
        "Consulting",
        "Marketing",
    ]

    manufacturing = _base_template(
        "SourceForge Market",
        "Match manufacturers with verified component buyers.",
        "Manufacturing",
    )
    manufacturing["participant_types"][0]["slug"] = "manufacturer"
    manufacturing["participant_types"][0]["name"] = "Manufacturer"
    manufacturing["participant_types"][1]["slug"] = "buyer"
    manufacturing["participant_types"][1]["name"] = "Buyer"
    manufacturing["profile_schemas"] = {
        "manufacturer": {
            "sections": [
                {
                    "name": "Capabilities",
                    "fields": [
                        {
                            "name": "company_name",
                            "label": "Company Name",
                            "type": "text",
                            "required": True,
                            "options": None,
                            "visibility": "public",
                            "searchable": True,
                        },
                        {
                            "name": "materials",
                            "label": "Materials Supported",
                            "type": "multi_select",
                            "required": True,
                            "options": ["Steel", "Aluminum", "Plastic", "Composite"],
                            "visibility": "public",
                            "searchable": True,
                        },
                        {
                            "name": "certifications",
                            "label": "Certifications",
                            "type": "multi_select",
                            "required": False,
                            "options": ["ISO 9001", "IATF 16949", "AS9100"],
                            "visibility": "public",
                            "searchable": True,
                        },
                    ],
                }
            ]
        },
        "buyer": deepcopy(_base_template("", "", "")["profile_schemas"]["client"]),
    }
    manufacturing["onboarding"] = {
        "manufacturer": {
            "requires_approval": True,
            "approval_type": "manual",
            "document_upload_required": True,
            "ai_extraction_enabled": True,
            "ai_profile_generation": True,
            "welcome_email_on_approval": True,
            "profile_completeness_threshold": 90,
        },
        "buyer": {
            "requires_approval": False,
            "approval_type": "auto",
            "document_upload_required": False,
            "ai_extraction_enabled": False,
            "ai_profile_generation": False,
            "welcome_email_on_approval": True,
            "profile_completeness_threshold": 100,
        },
    }
    manufacturing["communication"]["conversation_rules"][0] = {
        "initiator": "buyer",
        "receiver": "manufacturer",
        "requires_approval": True,
    }
    manufacturing["discovery"]["searchable_types"] = ["manufacturer"]
    manufacturing["discovery"]["filter_fields"] = ["materials", "certifications"]

    agriculture = _base_template(
        "AgriExchange",
        "Connect agricultural producers with wholesale buyers.",
        "Agriculture",
    )
    agriculture["participant_types"][0]["slug"] = "producer"
    agriculture["participant_types"][0]["name"] = "Producer"
    agriculture["participant_types"][1]["slug"] = "buyer"
    agriculture["participant_types"][1]["name"] = "Buyer"
    agriculture["profile_schemas"] = {
        "producer": {
            "sections": [
                {
                    "name": "Farm Profile",
                    "fields": [
                        {
                            "name": "farm_name",
                            "label": "Farm Name",
                            "type": "text",
                            "required": True,
                            "options": None,
                            "visibility": "public",
                            "searchable": True,
                        },
                        {
                            "name": "country",
                            "label": "Country",
                            "type": "text",
                            "required": True,
                            "options": None,
                            "visibility": "public",
                            "searchable": True,
                        },
                        {
                            "name": "primary_crops",
                            "label": "Primary Crops",
                            "type": "multi_select",
                            "required": True,
                            "options": ["Wheat", "Barley", "Corn", "Rice"],
                            "visibility": "public",
                            "searchable": True,
                        },
                    ],
                }
            ]
        },
        "buyer": deepcopy(_base_template("", "", "")["profile_schemas"]["client"]),
    }
    agriculture["onboarding"] = {
        "producer": {
            "requires_approval": True,
            "approval_type": "manual",
            "document_upload_required": True,
            "ai_extraction_enabled": True,
            "ai_profile_generation": True,
            "welcome_email_on_approval": True,
            "profile_completeness_threshold": 80,
        },
        "buyer": {
            "requires_approval": False,
            "approval_type": "auto",
            "document_upload_required": False,
            "ai_extraction_enabled": False,
            "ai_profile_generation": False,
            "welcome_email_on_approval": True,
            "profile_completeness_threshold": 100,
        },
    }
    agriculture["communication"]["conversation_rules"][0] = {
        "initiator": "buyer",
        "receiver": "producer",
        "requires_approval": True,
    }
    agriculture["discovery"]["searchable_types"] = ["producer"]
    agriculture["discovery"]["filter_fields"] = ["country", "primary_crops"]

    return [
        {
            "id": "agriculture_b2b",
            "title": "Agriculture Marketplace",
            "description": "Best for matching producers with buyers.",
            "when_to_use": "You have suppliers listing products and buyers searching/inquiring.",
            "config": agriculture,
        },
        {
            "id": "services_b2b",
            "title": "B2B Services Marketplace",
            "description": "Best for consulting and professional services platforms.",
            "when_to_use": "You match service providers with organizations seeking services.",
            "config": b2b_services,
        },
        {
            "id": "manufacturing_b2b",
            "title": "Manufacturing Sourcing Marketplace",
            "description": "Best for manufacturers and procurement teams.",
            "when_to_use": "You need capability-based supplier discovery and buyer outreach.",
            "config": manufacturing,
        },
    ]
