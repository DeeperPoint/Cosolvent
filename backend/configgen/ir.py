"""Intermediate representation for the marketplace.yaml generator.

The pipeline is: domain documents -> CommonContext domain schema -> *MarketDefinition*
(this module) -> assembled marketplace.yaml dict -> validated MarketplaceConfig.

MarketDefinition is participant-type oriented (who + their profile), which is the
shape ``marketplace.yaml`` needs. The CommonContext domain schema, by contrast, is
deal-entity oriented (goods / quantity / parties). The "pivot" between the two lives
in ``extract.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

RoleKind = Literal["supply", "demand", "facilitator"]
FieldType = Literal[
    "text", "number", "select", "multi_select", "date", "file", "files", "rich_text", "location"
]
Visibility = Literal["public", "protected", "private"]


@dataclass
class FieldDef:
    """One profile field, plus a provenance pointer back to the source schema path."""

    name: str
    label: str
    type: FieldType
    required: bool = False
    options: list[str] | None = None
    accepted_types: list[str] | None = None
    visibility: Visibility = "public"
    searchable: bool = False
    # Provenance: where in the domain schema (or which doc) this came from. Carried for
    # the human-review gate; not emitted into marketplace.yaml.
    source: str | None = None


@dataclass
class Section:
    name: str
    fields: list[FieldDef] = field(default_factory=list)


@dataclass
class ParticipantDef:
    name: str            # display name, e.g. "Seller"
    slug: str            # e.g. "seller"
    role: RoleKind
    description: str = ""
    sections: list[Section] = field(default_factory=list)
    # Subtypes collapsed into this one participant type, when a schema names more
    # facilitator subtypes than the remaining participant-type budget allows to each
    # get their own type (see extract.py::_facilitator_participants). Recorded so the
    # review gate can surface the lossy collapse. Cosolvent ROADMAP "Conflict C3" is
    # resolved (MAX_PARTICIPANT_TYPES > 3); this now only fires on a genuinely large
    # subtype list.
    collapsed_subtypes: list[str] = field(default_factory=list)


@dataclass
class MarketDefinition:
    name: str
    description: str
    industry: str
    vertical: str
    participants: list[ParticipantDef] = field(default_factory=list)
    #: Optional matching policy carried from the domain schema (GAP-3). Currently holds
    #: ``{"hard_gates": {<target slug|role>: [ {name, field, op, value}, ... ]}}``; weighted
    #: slots are still derived deterministically from the shared searchable fields.
    matching: dict = field(default_factory=dict)
