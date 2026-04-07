"""Dynamic Pydantic model generation from marketplace config field definitions.

Given a profile schema from config, generates Pydantic models at runtime using
pydantic.create_model(). Models are cached per type_slug.
"""

from __future__ import annotations

from typing import Any

from pydantic import create_model

from app.core.marketplace_config import FieldDefinition, MarketplaceConfig, ProfileSchema

# type → Python type mapping
_TYPE_MAP: dict[str, type] = {
    "text": str,
    "rich_text": str,
    "number": float,
    "select": str,
    "multi_select": list[str],
    "date": str,
    "file": str,
    "files": list,
    "location": dict,
}

_model_cache: dict[str, type] = {}


def _python_type(field: FieldDefinition) -> type:
    return _TYPE_MAP.get(field.type, str)


def get_profile_model(config: MarketplaceConfig, type_slug: str) -> type:
    """Return a cached dynamic Pydantic model for the given participant type's profile fields."""
    if type_slug in _model_cache:
        return _model_cache[type_slug]

    schema: ProfileSchema | None = config.profile_schemas.get(type_slug)
    if schema is None:
        raise ValueError(f"No profile schema for type '{type_slug}'")

    field_definitions: dict[str, Any] = {}
    for field in schema.all_fields:
        py_type = _python_type(field)
        if field.required:
            field_definitions[field.name] = (py_type, ...)
        else:
            field_definitions[field.name] = (py_type | None, None)

    model = create_model(f"{type_slug.title()}Profile", **field_definitions)
    _model_cache[type_slug] = model
    return model


def validate_profile_fields(
    config: MarketplaceConfig, type_slug: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate a dict of profile fields against the config-defined schema.

    Returns the validated (and coerced) dict. Raises ValidationError on bad data.
    """
    model = get_profile_model(config, type_slug)
    instance = model(**data)
    return instance.model_dump()


def compute_completeness(config: MarketplaceConfig, type_slug: str, fields: dict) -> int:
    """Return profile completeness as an integer percentage (0-100)."""
    schema = config.profile_schemas.get(type_slug)
    if not schema:
        return 0
    required_fields = [f for f in schema.all_fields if f.required]
    if not required_fields:
        return 100
    filled = sum(1 for f in required_fields if fields.get(f.name) not in (None, "", []))
    return int((filled / len(required_fields)) * 100)


def clear_cache() -> None:
    """Clear the model cache (useful in tests)."""
    _model_cache.clear()
