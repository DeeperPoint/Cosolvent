from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CreateDealRequest(BaseModel):
    """Create a deal from a conversation (preferred) or directly with a counterparty.

    The platform composes the first (anonymous) story version automatically — a match
    exists, so the deal begins with a Stage-1 Content Match Story awaiting acknowledgment.
    """

    conversation_id: str | None = None
    counterparty_user_id: str | None = None
    #: n-party (GAP-16 foundation): additional principals beyond the single counterparty.
    #: The party set and per-version required-acknowledgers are n-ary, so 3+ principals work.
    counterparty_user_ids: list[str] | None = None
    context: str | None = None
    #: which of the five deal-framework scenarios this deal starts from (provenance).
    framework_scenario: (
        Literal["industry_standard", "dominant_party", "no_framework", "regulatory_mandate", "repeat_precedent"]
        | None
    ) = None


class ParameterContribution(BaseModel):
    key: str
    label: str | None = None
    value: str | None = None
    unit: str | None = None


class RespondRequest(BaseModel):
    """Respond to a specific story version. Exactly three response kinds exist (§5).

    ``content_hash`` pins the response to the exact content the party was shown
    (integrity rule 2); a mismatch is rejected.
    """

    type: Literal["acknowledge", "annotate", "correct"]
    content_hash: str
    text: str | None = None
    params: list[ParameterContribution] = []


class SetInstrumentRequest(BaseModel):
    instrument: str


class ConsentRequest(BaseModel):
    """An authorization act (distinct from acknowledgment).

    * ``disclosure_advance`` — mutual opt-in to reveal identities (GAP-6). ``target`` is
      the level being advanced to (defaults to the next level).
    * ``audience_expansion`` — allow a joining facilitator to read the current milestone;
      ``target`` is the facilitator's user id.
    * ``attribute`` — allow a named protected attribute into a version; ``target`` is the key.
    """

    scope: Literal["disclosure_advance", "audience_expansion", "attribute"] = "disclosure_advance"
    target: str | None = None


class FacilitatorSlotRequest(BaseModel):
    role_type: str
    status: Literal["needed", "confirmed", "waived"] = "confirmed"
    user_id: str | None = None
    note: str | None = None


class FacilitatorSearchRequest(BaseModel):
    """Search facilitator participants of ``role_type`` matched to this deal (GAP-7).

    With ``name`` set, match facilitator profiles by company name instead of ranking
    them semantically against the deal's story.
    """

    role_type: str
    name: str | None = None


class ReopenRequest(BaseModel):
    matter: str | None = None


class AttachDocumentRequest(BaseModel):
    file_id: str
