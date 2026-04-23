"""marketplace.yaml → runtime rule contract.

The marketplace config is the source of truth for **business rules** that
don't appear in the OpenAPI spec:

- Which participant types exist and what roles they map to.
- Required fields per participant type.
- Whether public signup / public application is allowed.
- Whether a participant type requires onboarding documents or admin approval.
- Conversation initiation rules.
- Discovery search/visibility rules.

This module loads ``marketplace.yaml`` (the active, committed file) and
exposes typed accessors used by contract assertions in the e2e suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_YAML_PATH = _REPO_ROOT / "marketplace.yaml"


@dataclass(frozen=True)
class ParticipantContract:
    slug: str
    role: str
    permissions: dict[str, bool]
    required_fields: list[str]
    searchable_fields: list[str]
    public_fields: list[str]
    requires_approval: bool
    document_upload_required: bool


@dataclass(frozen=True)
class MarketplaceContract:
    """Strongly-typed projection of marketplace.yaml for runtime checks."""

    raw: dict[str, Any]
    source_path: Path

    @property
    def participant_types(self) -> list[ParticipantContract]:
        result: list[ParticipantContract] = []
        schemas = self.raw.get("profile_schemas", {}) or {}
        onboarding = self.raw.get("onboarding", {}) or {}
        for pt in self.raw.get("participant_types", []) or []:
            slug = pt.get("slug")
            if not slug:
                continue
            fields = _flatten_fields(schemas.get(slug, {}))
            ob = onboarding.get(slug, {}) or {}
            permissions = dict(pt.get("permissions") or {})
            result.append(
                ParticipantContract(
                    slug=str(slug),
                    role=str(pt.get("role", "")),
                    permissions=permissions,
                    required_fields=[f["name"] for f in fields if f.get("required")],
                    searchable_fields=[f["name"] for f in fields if f.get("searchable")],
                    public_fields=[
                        f["name"] for f in fields if f.get("visibility") == "public"
                    ],
                    requires_approval=bool(
                        ob.get("requires_approval")
                        or permissions.get("requires_approval")
                    ),
                    document_upload_required=bool(ob.get("document_upload_required")),
                )
            )
        return result

    def participant(self, slug: str) -> ParticipantContract | None:
        return next((p for p in self.participant_types if p.slug == slug), None)

    @property
    def allow_public_signup(self) -> bool:
        return bool((self.raw.get("auth") or {}).get("allow_public_signup", False))

    @property
    def allow_public_application(self) -> bool:
        return bool((self.raw.get("auth") or {}).get("allow_public_application", False))

    @property
    def searchable_types(self) -> list[str]:
        return list((self.raw.get("discovery") or {}).get("searchable_types", []))

    @property
    def conversation_rules(self) -> list[dict[str, Any]]:
        return list(
            ((self.raw.get("communication") or {}).get("conversation_rules") or [])
        )

    def conversation_rule(self, initiator: str, receiver: str) -> dict[str, Any] | None:
        for rule in self.conversation_rules:
            if rule.get("initiator") == initiator and rule.get("receiver") == receiver:
                return rule
        return None


def load_marketplace_contract(path: Path | None = None) -> MarketplaceContract:
    yaml_path = path or _DEFAULT_YAML_PATH
    with yaml_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return MarketplaceContract(raw=raw, source_path=yaml_path)


def _flatten_fields(schema: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for section in schema.get("sections", []) or []:
        for field in section.get("fields", []) or []:
            if isinstance(field, dict) and field.get("name"):
                fields.append(field)
    return fields
