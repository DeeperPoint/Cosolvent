"""YAML marketplace config loader + Pydantic validation models.

The marketplace.yaml file is the single source of truth for all runtime behaviour.
This module loads it, validates it, and exposes typed models for the rest of the app.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_ROLE_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")

# Max participant types allowed in one marketplace. Raised from the original MVP cap
# of 3 (ROADMAP "Conflict C3") so a market can have multiple types per role kind.
MAX_PARTICIPANT_TYPES = 8

_RESERVED_ROLE_SLUGS = {
    "admin",
    "auth",
    "search",
    "files",
    "notifications",
    "setup",
    "docs",
    "openapi",
    "roles",
    "ws",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Field definition inside a profile schema section ──────────────────────

_VALID_ACCEPTED_TYPES = {"image", "pdf", "document"}


class FieldDefinition(StrictModel):
    name: str
    label: str
    type: Literal["text", "number", "select", "multi_select", "date", "file", "files", "rich_text", "location"]
    required: bool = False
    options: list[str] | None = None
    accepted_types: list[str] | None = None
    visibility: Literal["public", "protected", "private"] = "public"
    searchable: bool = False

    @field_validator("options")
    @classmethod
    def options_required_for_select(cls, v: list[str] | None, info) -> list[str] | None:
        if info.data.get("type") in ("select", "multi_select") and not v:
            raise ValueError("options required for select/multi_select fields")
        return v

    @field_validator("accepted_types")
    @classmethod
    def validate_accepted_types(cls, v: list[str] | None, info) -> list[str] | None:
        field_type = info.data.get("type")
        if field_type != "files":
            if v is not None:
                raise ValueError("accepted_types is only valid for 'files' field type")
            return None
        if v is None:
            return ["image", "pdf"]
        invalid = set(v) - _VALID_ACCEPTED_TYPES
        if invalid:
            raise ValueError(f"Invalid accepted_types: {sorted(invalid)}. Valid: {sorted(_VALID_ACCEPTED_TYPES)}")
        return v


class ProfileSection(StrictModel):
    name: str
    fields: list[FieldDefinition]


class ProfileSchema(StrictModel):
    sections: list[ProfileSection]

    @property
    def all_fields(self) -> list[FieldDefinition]:
        return [f for s in self.sections for f in s.fields]

    def get_field(self, name: str) -> FieldDefinition | None:
        for f in self.all_fields:
            if f.name == name:
                return f
        return None


# ── Participant type permissions ──────────────────────────────────────────

class ParticipantPermissions(StrictModel):
    can_list: bool = False
    can_search: bool = False
    can_initiate_conversation: bool = False
    can_receive_conversation: bool = False
    can_share_private_assets: bool = False
    requires_onboarding: bool = True
    requires_approval: bool = False
    visible_in_search: bool = False


class ParticipantType(StrictModel):
    name: str
    slug: str
    role: Literal["supply", "demand", "facilitator"]
    permissions: ParticipantPermissions


# ── Onboarding settings per type ─────────────────────────────────────────

class OnboardingConfig(StrictModel):
    requires_approval: bool = True
    approval_type: Literal["manual", "auto"] = "manual"
    document_upload_required: bool = False
    ai_extraction_enabled: bool = False
    ai_profile_generation: bool = False
    welcome_email_on_approval: bool = True
    profile_completeness_threshold: int = 100

    @field_validator("profile_completeness_threshold")
    @classmethod
    def validate_completeness_threshold(cls, v: int) -> int:
        if v < 0 or v > 100:
            raise ValueError("profile_completeness_threshold must be between 0 and 100")
        return v


# ── Communication rules ──────────────────────────────────────────────────

class ConversationRule(StrictModel):
    initiator: str
    receiver: str
    requires_approval: bool = True


class CommunicationConfig(StrictModel):
    conversation_rules: list[ConversationRule]


# ── Discovery / AI settings ──────────────────────────────────────────────

class ResultVisibility(StrictModel):
    anonymous: Literal["public"] = "public"
    authenticated: Literal["public", "protected"] = "protected"


class AIDiscoveryConfig(StrictModel):
    vector_search_enabled: bool = True
    rag_query_enabled: bool = True
    follow_up_suggestions: bool = True
    profile_retrieval_mode: Literal["hybrid", "rag_strict"] = "hybrid"
    rag_failure_behavior: Literal["service_unavailable", "empty"] = "service_unavailable"
    profile_similarity_threshold: float = 0.25
    max_vector_candidates: int = 500

    @field_validator("profile_similarity_threshold")
    @classmethod
    def validate_similarity_threshold(cls, v: float) -> float:
        if v < 0 or v > 1:
            raise ValueError("profile_similarity_threshold must be between 0 and 1")
        return v

    @field_validator("max_vector_candidates")
    @classmethod
    def validate_max_vector_candidates(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_vector_candidates must be >= 1")
        return v


class DiscoveryAccessConfig(StrictModel):
    anonymous_search_enabled: bool = False
    anonymous_filter_mode: Literal["public_only", "none", "all"] = "public_only"


# ── Match scoring & gating (GAP-3) ────────────────────────────────────────
# A weighted, config-driven scoring model layered over semantic similarity:
# composite = vector_weight * vector + Σ slot.weight * slot_score, and hard gates
# that exclude structurally incompatible candidates before they are ranked.

class MatchSlot(StrictModel):
    """One weighted soft dimension of the match score."""
    name: str
    fields: list[str]
    # How the slot's fields are compared into a [0,1] score:
    #   scalar_eq         — 1.0 if equal, else 0.0 (per field, averaged)
    #   jaccard           — set overlap (lists, or scalars as singletons)
    #   numeric_proximity — 1 - normalized absolute difference
    #   window_overlap    — date-range overlap / union (GAP-18: temporal
    #                       perishability, e.g. availability window vs. needed-by
    #                       window). Field value: [start, end] or {"start","end"}.
    comparator: Literal["scalar_eq", "jaccard", "numeric_proximity", "window_overlap"] = "scalar_eq"
    weight: float = Field(ge=0.0, le=1.0)


class HardGate(StrictModel):
    """A mandatory condition on a candidate field; failing it excludes the match."""
    name: str
    field: str
    op: Literal["equals", "in", "gte", "lte", "present"] = "equals"
    value: Any = None  # unused for op == "present"


class MatchProfile(StrictModel):
    """The scoring weight table + gates used against one target type."""
    vector_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    slots: list[MatchSlot] = []
    hard_gates: list[HardGate] = []

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> "MatchProfile":
        total = self.vector_weight + sum(s.weight for s in self.slots)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"matching weights must sum to 1.0 (vector_weight + slot weights = {total:.4f})"
            )
        names = [s.name for s in self.slots]
        if len(names) != len(set(names)):
            raise ValueError("matching slot names must be unique")
        return self


class MatchingConfig(StrictModel):
    """Optional per-target scoring/gating. Absent → the engine uses its legacy
    semantic + field-overlap blend, so existing configs keep working unchanged."""
    default: MatchProfile | None = None
    per_target: dict[str, MatchProfile] = {}

    def profile_for(self, target_type: str) -> MatchProfile | None:
        return self.per_target.get(target_type) or self.default


class DiscoveryConfig(StrictModel):
    searchable_types: list[str]
    filter_fields: list[str] = []
    result_visibility: ResultVisibility = ResultVisibility()
    ai: AIDiscoveryConfig = AIDiscoveryConfig()
    access: DiscoveryAccessConfig = DiscoveryAccessConfig()
    matching: MatchingConfig = MatchingConfig()


# ── Marketplace identity ─────────────────────────────────────────────────

class MarketplaceIdentity(StrictModel):
    name: str
    description: str = ""
    industry: str = ""


class AuthConfig(StrictModel):
    """Public auth behaviour (self-service account creation vs application-only intake)."""

    allow_public_signup: bool = True
    #: Allow anonymous POST .../register to submit a pending application (no account yet).
    #: Independent of ``allow_public_signup`` so you can disable signup but still accept applications.
    allow_public_application: bool = True


# ── AI provider config ────────────────────────────────────────────────────

class AIConfig(StrictModel):
    enabled_providers: list[str] = ["openai"]


# ── Story Progression System (GAP-4) config ───────────────────────────────

# Standard, non-binding acknowledgment wording (integrity rule 7: it appears on the
# acknowledgment surface itself, every time — not only in a document footer).
_DEFAULT_SIGNOFF = (
    "I have read this summary and I have nothing to add or correct at this time. "
    "This is not an agreement to any terms and does not create any obligation."
)
_DEFAULT_FINAL_SIGNOFF = (
    "I have read this Deal Brief and it accurately captures our shared intent. "
    "It is a summary for our own use, not a contract."
)


class StoryProgressionConfig(StrictModel):
    """Per-vertical tuning of the deal-assembly story chain (see story-progression-system §11)."""

    #: published → stale (dormancy, never death). Days.
    acknowledgment_window_days: int = 14
    #: show "waiting on party X" to the other parties. Social-pressure lever — OFF by default.
    pending_visibility: bool = False
    #: reminder schedule after publication, in days.
    reminder_cadence_days: list[int] = [3, 7]
    #: the Content Match Story's three stages; advancing requires consent from every principal.
    disclosure_levels: list[str] = ["anonymous", "named", "deal_context"]
    #: copy key identifying the non-binding final wording (kept for manual/UI parity).
    final_wording_key: str = "brief_signoff"
    #: the non-binding wording shown on every ordinary acknowledgment.
    signoff_wording: str = _DEFAULT_SIGNOFF
    #: the non-binding wording shown on the final Deal-Brief acknowledgment.
    final_signoff_wording: str = _DEFAULT_FINAL_SIGNOFF
    #: snapshot keys treated as non-shareable (Loop-3). A protected value is redacted from a
    #: published version until its owning party consents to disclose it for that audience.
    #: Matched case-insensitively as substrings of the parameter key.
    protected_attributes: list[str] = [
        "price", "pricing", "reserve", "margin", "cost", "utilization",
        "utilisation", "budget", "floor", "discount",
    ]

    @field_validator("acknowledgment_window_days")
    @classmethod
    def _validate_window(cls, v: int) -> int:
        if v < 1:
            raise ValueError("acknowledgment_window_days must be >= 1")
        return v

    @field_validator("disclosure_levels")
    @classmethod
    def _validate_levels(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("disclosure_levels must not be empty")
        return v


class DealInstrument(StrictModel):
    """A deal instrument + its Deal-Brief template (GAP-5/GAP-15).

    ``required_fields`` doubles as the ``deal_brief_template.yaml`` for this instrument:
    it documents the instrument AND defines the completeness guard that unlocks the
    final acknowledgment. An instrument with no complete template is *unfinishable*.
    """

    name: str
    label: str
    description: str = ""
    #: field keys the deal's structured snapshot must carry to be template-complete.
    required_fields: list[str] = []

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not _ROLE_SLUG_RE.match(v):
            raise ValueError(
                f"Invalid instrument name '{v}'. Use lowercase letters, numbers, '_' or '-', 2-64 chars."
            )
        return v


def _default_deal_instruments() -> list[DealInstrument]:
    """Baseline instrument vocabulary. GAP-15 requires the two loan-like instruments
    (``capacity_rental``, ``reciprocity_preference``) to exist so a demo never fails
    its own anchor story's release-gate check."""
    return [
        DealInstrument(
            name="spot_purchase",
            label="Spot Purchase",
            description="A one-off transfer of goods/services at an agreed price.",
            required_fields=["instrument", "parties", "product", "quantity", "price", "delivery_window"],
        ),
        DealInstrument(
            name="capacity_rental",
            label="Capacity Rental",
            description="Time-boxed rental of productive capacity, operator optionally included "
            "(closer to a soccer loan than a commodity transaction).",
            required_fields=[
                "instrument",
                "parties",
                "scope",
                "rate",
                "delivery_window",
                "operator_included",
                "facilitator_confirmations",
            ],
        ),
        DealInstrument(
            name="reciprocity_preference",
            label="Reciprocity Preference",
            description="A registered, non-binding preference to reciprocate capacity/work in future.",
            required_fields=["instrument", "parties", "scope", "reciprocity_terms"],
        ),
    ]


# ── Root config ──────────────────────────────────────────────────────────

class MarketplaceConfig(StrictModel):
    marketplace: MarketplaceIdentity
    participant_types: list[ParticipantType]
    profile_schemas: dict[str, ProfileSchema]
    onboarding: dict[str, OnboardingConfig]
    communication: CommunicationConfig
    discovery: DiscoveryConfig
    ai: AIConfig = AIConfig()
    auth: AuthConfig = AuthConfig()
    # Deal-assembly layer (optional; sensible defaults so existing configs keep working).
    story_progression: StoryProgressionConfig = StoryProgressionConfig()
    deal_instruments: list[DealInstrument] = []

    # ── helpers ───────────────────────────────────────────────────────
    def get_type(self, slug: str) -> ParticipantType | None:
        for pt in self.participant_types:
            if pt.slug == slug:
                return pt
        return None

    def type_slugs(self) -> list[str]:
        return [pt.slug for pt in self.participant_types]

    def instruments(self) -> list[DealInstrument]:
        """Configured deal instruments, or the baseline vocabulary (incl. the GAP-15
        loan-like instruments) when the vertical config omits the block."""
        return self.deal_instruments or _default_deal_instruments()

    def get_instrument(self, name: str) -> DealInstrument | None:
        for inst in self.instruments():
            if inst.name == name:
                return inst
        return None

    # ── cross-validation ─────────────────────────────────────────────
    @model_validator(mode="after")
    def cross_validate(self) -> "MarketplaceConfig":
        slug_list = self.type_slugs()
        slugs = set(slug_list)

        # Need at least 2 participant types (a market needs both sides of an exchange).
        # Upper bound relaxes the original MVP cap of 3 (ROADMAP "Conflict C3", option A):
        # multiple types may share a role kind, e.g. several distinct facilitators
        # (inspector, carrier, financier). Matching, permissions, communication, and both
        # compilers iterate types generically, so any count in range works.
        if len(self.participant_types) < 2:
            raise ValueError("At least 2 participant types required")
        if len(self.participant_types) > MAX_PARTICIPANT_TYPES:
            raise ValueError(f"Maximum {MAX_PARTICIPANT_TYPES} participant types")

        if len(slugs) != len(slug_list):
            duplicate_slugs = sorted({slug for slug in slug_list if slug_list.count(slug) > 1})
            duplicates = ", ".join(duplicate_slugs)
            raise ValueError(f"Duplicate participant slug(s) are not allowed: {duplicates}")

        for slug in slug_list:
            if not _ROLE_SLUG_RE.match(slug):
                raise ValueError(
                    f"Invalid participant slug '{slug}'. Use lowercase letters, numbers, '_' or '-', 2-64 chars."
                )
            if slug in _RESERVED_ROLE_SLUGS:
                raise ValueError(
                    f"Participant slug '{slug}' is reserved and cannot be used for generated role aliases."
                )

        # Profile schemas must exist for every participant type
        for slug in slugs:
            if slug not in self.profile_schemas:
                raise ValueError(f"Missing profile schema for participant type '{slug}'")

        # Onboarding config must exist for every participant type
        for slug in slugs:
            if slug not in self.onboarding:
                raise ValueError(f"Missing onboarding config for participant type '{slug}'")

        # Conversation rules must reference valid type slugs
        for rule in self.communication.conversation_rules:
            if rule.initiator not in slugs:
                raise ValueError(
                    f"Conversation rule references unknown initiator type '{rule.initiator}'"
                )
            if rule.receiver not in slugs:
                raise ValueError(
                    f"Conversation rule references unknown receiver type '{rule.receiver}'"
                )

        # At least one type must can_search
        if not any(pt.permissions.can_search for pt in self.participant_types):
            raise ValueError("At least one participant type must have can_search=true")

        # At least one type must be visible_in_search
        if not any(pt.permissions.visible_in_search for pt in self.participant_types):
            raise ValueError("At least one participant type must have visible_in_search=true")

        # Searchable types in discovery must reference valid slugs
        for st in self.discovery.searchable_types:
            if st not in slugs:
                raise ValueError(f"Discovery searchable_types references unknown type '{st}'")
            pt = self.get_type(st)
            if pt and not pt.permissions.visible_in_search:
                raise ValueError(
                    f"Discovery searchable_type '{st}' must have visible_in_search=true"
                )

        # Filter fields must exist in at least one profile schema
        all_field_names = set()
        for schema in self.profile_schemas.values():
            for f in schema.all_fields:
                all_field_names.add(f.name)
        for ff in self.discovery.filter_fields:
            if ff not in all_field_names:
                raise ValueError(f"Discovery filter_field '{ff}' not found in any profile schema")

        # Matching config: per_target keys must be valid slugs; slot/gate fields must exist.
        matching = self.discovery.matching
        for tgt in matching.per_target:
            if tgt not in slugs:
                raise ValueError(f"Discovery matching per_target references unknown type '{tgt}'")
        for mp in [matching.default, *matching.per_target.values()]:
            if mp is None:
                continue
            for slot in mp.slots:
                for fld in slot.fields:
                    if fld not in all_field_names:
                        raise ValueError(
                            f"Matching slot '{slot.name}' references unknown field '{fld}'"
                        )
            for gate in mp.hard_gates:
                if gate.field not in all_field_names:
                    raise ValueError(
                        f"Matching hard_gate '{gate.name}' references unknown field '{gate.field}'"
                    )

        return self


def load_marketplace_config(path: str | Path) -> MarketplaceConfig:
    """Load and validate a marketplace YAML config file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Marketplace config not found: {path}")
    raw: dict[str, Any] = yaml.safe_load(path.read_text())
    return MarketplaceConfig(**raw)


# ── Module-level singleton (set during app startup) ──────────────────────

_config: MarketplaceConfig | None = None


def get_marketplace_config() -> MarketplaceConfig:
    if _config is None:
        raise RuntimeError("Marketplace config not loaded. Call load_marketplace_config first.")
    return _config


def set_marketplace_config(cfg: MarketplaceConfig) -> None:
    global _config
    _config = cfg
