from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CreateDealRequest(BaseModel):
    """Create a deal from a conversation (preferred) or directly with a counterparty."""

    conversation_id: str | None = None
    counterparty_user_id: str | None = None
    context: str | None = None


class UpdateDealRequest(BaseModel):
    context: str | None = None


class ParameterRequest(BaseModel):
    """Add or update a recorded deal term (upsert by ``key``)."""

    key: str
    label: str | None = None
    value: str | None = None
    unit: str | None = None
    agreed: bool | None = None
    note: str | None = None


class FacilitatorSlotRequest(BaseModel):
    """Fill / confirm / waive a facilitator role slot."""

    role_type: str
    status: Literal["needed", "confirmed", "waived"] = "confirmed"
    user_id: str | None = None
    note: str | None = None


class AttachDocumentRequest(BaseModel):
    file_id: str


# ── Response shapes (documentation for the OpenAPI contract) ─────────────────
class DealParameter(BaseModel):
    key: str
    label: str | None = None
    value: str | None = None
    unit: str | None = None
    agreed: bool = False
    note: str | None = None


class FacilitatorSlot(BaseModel):
    role_type: str
    status: Literal["needed", "confirmed", "waived"] = "needed"
    user_id: str | None = None
    note: str | None = None


class DealBrief(BaseModel):
    markdown: str
    citations: list[dict] = []
    use_case: str | None = None
    generated_at: str | None = None


class DealResponse(BaseModel):
    id: str
    status: str  # draft | active | agreed | brief_ready | handoff | cancelled
    vertical: str | None = None
    conversation_id: str | None = None
    principals: list[dict] = []
    participants: list[dict] = []
    facilitator_slots: list[dict] = []
    parameters: list[dict] = []
    documents: list[str] = []
    context: str | None = None
    brief: dict | None = None
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
