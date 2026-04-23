"""Shared response envelopes.

Used as ``response_model=...`` on endpoints whose return type is a
hand-crafted dict rather than a full Pydantic model.  Declaring them
explicitly ensures every operation has a JSON schema in the generated
OpenAPI spec, which is required for contract-level type safety and for
``ContractClient`` to validate runtime responses.

Intentionally permissive (``extra="allow"`` via ``model_config``) so we
don't break on legacy callers that add ad-hoc fields; tightening is
done per-endpoint with domain-specific Pydantic models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, RootModel


class DetailResponse(BaseModel):
    """Simple ``{"detail": "..."}`` acknowledgement payload."""

    detail: str


class DeletedResponse(BaseModel):
    """Result of a delete operation."""

    model_config = ConfigDict(extra="allow")
    deleted: bool = True


class OkResponse(BaseModel):
    """Generic success payload used where the body is informational."""

    model_config = ConfigDict(extra="allow")
    ok: bool = True


class JSONObject(RootModel[dict[str, Any]]):
    """Free-form JSON object — emits ``{"type": "object"}`` in OpenAPI."""


class JSONList(RootModel[list[dict[str, Any]]]):
    """Free-form JSON array of objects — emits ``{"type": "array"}``."""


class StringList(RootModel[list[str]]):
    """JSON array of strings."""
