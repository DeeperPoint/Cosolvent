"""The pivot: CommonContext domain schema -> participant-oriented MarketDefinition.

Deterministic baseline. It produces a valid, domain-grounded MarketDefinition with no
LLM required, by reading the schema's ``participant_roles`` mapping and projecting the
controlled vocabulary onto each participant's profile. An optional LLM enrichment pass
(``llm.py``) can refine field selection/labels afterwards.
"""

from __future__ import annotations

import re

from app.core.marketplace_config import MAX_PARTICIPANT_TYPES

from .domain_schema import DomainSchema
from .ir import FieldDef, MarketDefinition, ParticipantDef, RoleKind, Section

_RESERVED = {"admin", "auth", "search", "files", "notifications", "setup", "docs", "openapi", "roles", "ws"}
_DEFAULT_SLUG = {"supply": "seller", "demand": "buyer", "facilitator": "provider"}
_DEFAULT_LABEL = {"supply": "Seller", "demand": "Buyer", "facilitator": "Provider"}
_DEFAULT_COUNTRIES = ["USA", "Canada", "Mexico", "Germany", "Brazil", "India", "China", "Japan"]
_DEFAULT_REGIONS = [
    "North America", "South America", "Europe", "Middle East",
    "Africa", "South Asia", "East Asia", "Southeast Asia", "Oceania",
]


def _slug(text: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9_-]+", "_", text.strip().lower()).strip("_-")
    if not re.match(r"^[a-z][a-z0-9_-]{1,63}$", s) or s in _RESERVED:
        return fallback
    return s


def _humanize(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").strip().title()


def _identity_section(role: RoleKind, schema: DomainSchema) -> Section:
    countries = schema.field_values("goods", "origin_country") or _DEFAULT_COUNTRIES
    noun = {"supply": "Company", "demand": "Organization", "facilitator": "Company"}[role]
    return Section(
        name=noun,
        fields=[
            FieldDef("company_name", f"{noun} Name", "text", required=True, visibility="public", searchable=True),
            FieldDef("country", "Country", "select", required=True, options=list(countries),
                     visibility="public", searchable=True, source="goods.origin_country"),
            FieldDef("description", "About", "rich_text", required=False, visibility="public", searchable=True),
        ],
    )


# Fields skipped when projecting a section onto a profile (handled elsewhere or noise).
_SKIP_FIELDS = {"origin_country", "description"}


def _project_section(schema: DomainSchema, section: str, *, visibility: str) -> list[FieldDef]:
    """Turn every controlled-vocabulary / numeric field in a schema section into a
    profile FieldDef. ``allowed_values``/``examples`` → (multi_)select; numbers → number."""
    out: list[FieldDef] = []
    for name, spec in schema.section_field_specs(section):
        if name in _SKIP_FIELDS:
            continue
        allowed = spec.get("allowed_values")
        examples = spec.get("examples")
        values = allowed if isinstance(allowed, list) and allowed else examples
        if isinstance(values, list) and values:
            # A vocab field is multi_select by default; declare ``cardinality: single``
            # (or ``multi: false``) in the schema for a single-choice select.
            single = spec.get("cardinality") == "single" or spec.get("multi") is False
            out.append(FieldDef(
                name=name, label=_humanize(name), type="select" if single else "multi_select",
                required=bool(spec.get("required", False)),
                options=[str(v) for v in values], visibility=visibility, searchable=True,
                source=f"{section}.{name}",
            ))
        elif spec.get("type") in ("number", "integer", "float"):
            out.append(FieldDef(
                name=name, label=_humanize(name), type="number",
                required=bool(spec.get("required", False)),
                visibility=visibility, searchable=True, source=f"{section}.{name}",
            ))
    return out


def _primary_domain_sections(schema: DomainSchema) -> list[str]:
    """Which domain-schema section(s) describe the tradeable good/service.

    Prefers the legacy ``goods`` convention (grain_trade_schema.yaml and every
    schema written to match it — kept exact for backward compatibility with
    existing verticals' generated field sets). A schema that doesn't use that
    name falls back to every domain section it does have, instead of silently
    producing an empty Offering/Requirements profile: the synthesis prompt only
    *suggests* ``goods`` as one example section name among several, so plenty of
    valid schemas won't use it.
    """
    if schema.raw.get("goods"):
        return ["goods"]
    return schema.domain_sections()


def _project_sections(schema: DomainSchema, sections: list[str], *, visibility: str) -> list[FieldDef]:
    """``_project_section`` over multiple sections, de-duplicated by field name
    (first occurrence wins) in case two sections happen to name a field the same."""
    out: list[FieldDef] = []
    seen: set[str] = set()
    for section in sections:
        for f in _project_section(schema, section, visibility=visibility):
            if f.name in seen:
                continue
            seen.add(f.name)
            out.append(f)
    return out


def _supply_section(schema: DomainSchema) -> Section:
    fields = _project_sections(schema, _primary_domain_sections(schema), visibility="public")
    fields.append(FieldDef("spec_sheets", "Spec Sheets / Documents", "files", required=False,
                           accepted_types=["pdf"], visibility="private", searchable=False))
    return Section(name="Offering", fields=fields)


def _demand_section(schema: DomainSchema) -> Section:
    # Same vocabulary as supply, framed as buyer interests (protected visibility).
    fields = _project_sections(schema, _primary_domain_sections(schema), visibility="protected")
    fields.append(FieldDef("budget_range", "Typical Budget per Order", "select", required=False,
                           options=["Under 25k", "25k-100k", "100k-500k", "500k-2M", "2M+"],
                           visibility="protected", searchable=False))
    return Section(name="Requirements", fields=fields)


def _facilitator_section(schema: DomainSchema, *, services_offered: bool = True) -> Section:
    """``services_offered=False`` for the one-type-per-subtype expansion (below): the
    participant type itself already names the service, so a 'which service do you
    offer' field on top of it would be redundant."""
    fields: list[FieldDef] = []
    if services_offered:
        subtypes = schema.facilitator_subtypes()
        services = [_humanize(s) for s in subtypes] or ["Logistics", "Inspection", "Finance", "Insurance"]
        fields.append(FieldDef("services_offered", "Services Offered", "multi_select", required=True,
                     options=services, visibility="public", searchable=True,
                     source="participant_roles.facilitator.subtypes"))
    fields.append(FieldDef("service_regions", "Service Regions", "multi_select", required=True,
                 options=list(_DEFAULT_REGIONS), visibility="public", searchable=True))
    # Project any logistics/service attributes the schema provides (equipment types, etc.).
    fields += _project_section(schema, "logistics", visibility="public")
    fields.append(FieldDef("credentials", "Credentials / Certificates", "files", required=False,
                           accepted_types=["pdf"], visibility="private", searchable=False))
    return Section(name="Services", fields=fields)


_ROLE_SECTION = {"supply": _supply_section, "demand": _demand_section, "facilitator": _facilitator_section}


def _facilitator_participants(
    schema: DomainSchema, info: dict, used_slugs: set[str], budget: int
) -> list[ParticipantDef]:
    """One participant type per facilitator subtype when the budget allows (e.g. a
    deal can then have distinct `quality_inspector` vs `logistics_provider` slots —
    see GAP-7 facilitator_slots, which is keyed one-slot-per-participant-type); a
    single collapsed 'Deal Facilitator' type otherwise. Historically this was always
    collapsed under a hard 3-type cap (Cosolvent ROADMAP Conflict C3); the engine's
    cap is `MAX_PARTICIPANT_TYPES` (currently well above 3), so expansion is the
    common case now — collapsing only when a schema genuinely has more subtypes than
    the remaining budget.
    """
    subtype_defs = schema.facilitator_subtype_defs()
    label = str(info.get("label") or _DEFAULT_LABEL["facilitator"])
    description = str(info.get("description", "")).strip()

    if not subtype_defs or len(subtype_defs) > budget:
        slug = _slug(label, _DEFAULT_SLUG["facilitator"])
        if slug in used_slugs:
            slug = _DEFAULT_SLUG["facilitator"]
        used_slugs.add(slug)
        sections = [_identity_section("facilitator", schema), _facilitator_section(schema)]
        return [ParticipantDef(
            name=label.split("/")[0].strip(), slug=slug, role="facilitator",
            description=description, sections=sections,
            collapsed_subtypes=schema.facilitator_subtypes(),
        )]

    out: list[ParticipantDef] = []
    for sub in subtype_defs:
        sub_label = _humanize(sub["role"])
        slug = _slug(sub["role"], _slug(sub_label, "provider"))
        if slug in used_slugs:
            slug = f"{slug}_2"
        used_slugs.add(slug)
        sections = [_identity_section("facilitator", schema), _facilitator_section(schema, services_offered=False)]
        out.append(ParticipantDef(
            name=sub_label, slug=slug, role="facilitator",
            description=sub["description"] or description, sections=sections,
        ))
    return out


def extract_market(schema: DomainSchema, *, name: str | None = None,
                   industry: str | None = None) -> MarketDefinition:
    """Build a MarketDefinition from a domain schema (deterministic pivot)."""
    roles = schema.participant_roles()
    if not roles:
        # Minimal viable market: every marketplace needs at least a supply and demand side.
        roles = {"supply": {}, "demand": {}}

    # At most one type per supply/demand role kind; facilitator may expand into
    # multiple types (see _facilitator_participants) within MAX_PARTICIPANT_TYPES.
    ordered: list[RoleKind] = [r for r in ("supply", "demand", "facilitator") if r in roles]

    participants: list[ParticipantDef] = []
    used_slugs: set[str] = set()
    non_facilitator_count = sum(1 for r in ordered if r != "facilitator")
    for role in ordered:
        info = roles.get(role, {})
        if role == "facilitator":
            budget = max(1, MAX_PARTICIPANT_TYPES - non_facilitator_count)
            participants.extend(_facilitator_participants(schema, info, used_slugs, budget))
            continue

        label = str(info.get("label") or _DEFAULT_LABEL[role])
        slug = _slug(label, _DEFAULT_SLUG[role])
        if slug in used_slugs:
            slug = _DEFAULT_SLUG[role]
        used_slugs.add(slug)

        sections = [_identity_section(role, schema), _ROLE_SECTION[role](schema)]
        participants.append(
            ParticipantDef(
                name=label.split("/")[0].strip(),
                slug=slug,
                role=role,
                description=str(info.get("description", "")).strip(),
                sections=sections,
            )
        )

    vertical = schema.vertical
    matching = schema.raw.get("matching") if isinstance(schema.raw.get("matching"), dict) else {}
    return MarketDefinition(
        name=name or _humanize(vertical),
        description=f"A thin-market marketplace for {_humanize(vertical)}.",
        industry=industry or _humanize(vertical),
        vertical=vertical,
        participants=participants,
        matching=matching or {},
    )
