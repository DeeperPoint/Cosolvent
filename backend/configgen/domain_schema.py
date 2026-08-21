"""Reader + accessors for a CommonContext domain schema (``<vertical>_schema.yaml``).

The domain schema is deal-entity oriented. This module loads it and exposes helpers
to pull out the parts the generator needs: the participant_roles mapping and the
controlled vocabulary embedded in ``allowed_values`` / ``examples`` / enum fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class VocabField:
    """A schema field that carries a controlled or example vocabulary."""

    path: str                 # dotted path, e.g. "goods.commodity_type"
    name: str                 # leaf name, e.g. "commodity_type"
    values: list[str]         # the vocabulary values
    hard: bool                # True if from allowed_values (lock), False if from examples (bias)
    required: bool
    description: str = ""


class DomainSchema:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw

    @classmethod
    def load(cls, path: str | Path) -> "DomainSchema":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Domain schema not found: {path}")
        return cls(yaml.safe_load(path.read_text()) or {})

    # ── identity ──────────────────────────────────────────────────────────
    @property
    def vertical(self) -> str:
        return str(self.raw.get("vertical") or self.raw.get("domain") or "marketplace")

    @property
    def source_authority(self) -> str:
        return str(self.raw.get("source_authority", ""))

    # ── participant roles ─────────────────────────────────────────────────
    def participant_roles(self) -> dict[str, dict[str, Any]]:
        """Return the participant_roles mapping (supply/demand/facilitator), if present.

        Each value is a dict that may contain ``label``, ``description``, and (for
        facilitator) ``subtypes: [{role, description}, ...]``.
        """
        pr = self.raw.get("participant_roles", {})
        if not isinstance(pr, dict):
            return {}
        return {k: v for k, v in pr.items() if k in ("supply", "demand", "facilitator") and isinstance(v, dict)}

    def facilitator_subtypes(self) -> list[str]:
        return [d["role"] for d in self.facilitator_subtype_defs()]

    def facilitator_subtype_defs(self) -> list[dict[str, str]]:
        """Each facilitator subtype as ``{"role": ..., "description": ...}``, in
        schema order. Used both to build the collapsed single-facilitator-type
        services vocabulary and (when the participant-type budget allows — see
        extract.py) to expand each subtype into its own participant type."""
        fac = self.participant_roles().get("facilitator", {})
        subs = fac.get("subtypes", []) if isinstance(fac, dict) else []
        out: list[dict[str, str]] = []
        for s in subs:
            if isinstance(s, dict) and s.get("role"):
                out.append({"role": str(s["role"]), "description": str(s.get("description", ""))})
        return out

    # ── field / vocabulary access ─────────────────────────────────────────
    def get_field(self, section: str, name: str) -> dict[str, Any] | None:
        sec = self.raw.get(section)
        if isinstance(sec, dict):
            fields = sec.get("fields")
            if isinstance(fields, dict):
                f = fields.get(name)
                if isinstance(f, dict):
                    return f
        return None

    def field_values(self, section: str, name: str) -> list[str]:
        """allowed_values, else examples, else []."""
        f = self.get_field(section, name)
        if not f:
            return []
        for key in ("allowed_values", "examples"):
            vals = f.get(key)
            if isinstance(vals, list) and vals:
                return [str(v) for v in vals]
        return []

    def section_field_specs(self, section: str) -> list[tuple[str, dict[str, Any]]]:
        """Return [(field_name, spec), ...] for ``<section>.fields`` in document order."""
        sec = self.raw.get(section)
        out: list[tuple[str, dict[str, Any]]] = []
        if isinstance(sec, dict) and isinstance(sec.get("fields"), dict):
            for name, spec in sec["fields"].items():
                if isinstance(spec, dict):
                    out.append((str(name), spec))
        return out

    _RESERVED_TOP_LEVEL = {
        "schema_version", "vertical", "domain", "source_authority", "governing_law",
        "participant_roles", "referenced_standards", "matching",
    }

    def domain_sections(self) -> list[str]:
        """Every top-level key that's a domain-content section (a dict with a
        ``fields`` dict), in document order — the schema's own vocabulary
        organization, whatever it chose to call its sections (``goods``, or
        ``capacity``/``material``/``quality``/... — the synthesis prompt only
        *suggests* ``goods`` as an example name, so a schema is free to name its
        sections however fits the domain)."""
        out: list[str] = []
        for key, body in self.raw.items():
            if key in self._RESERVED_TOP_LEVEL:
                continue
            if isinstance(body, dict) and isinstance(body.get("fields"), dict):
                out.append(str(key))
        return out

    def vocab_fields(self) -> list[VocabField]:
        """Walk every ``<section>.fields.<name>`` and collect controlled/example vocab."""
        out: list[VocabField] = []
        for section, body in self.raw.items():
            if not isinstance(body, dict):
                continue
            fields = body.get("fields")
            if not isinstance(fields, dict):
                continue
            for name, spec in fields.items():
                if not isinstance(spec, dict):
                    continue
                allowed = spec.get("allowed_values")
                examples = spec.get("examples")
                if isinstance(allowed, list) and allowed:
                    values, hard = [str(v) for v in allowed], True
                elif isinstance(examples, list) and examples:
                    values, hard = [str(v) for v in examples], False
                else:
                    continue
                out.append(
                    VocabField(
                        path=f"{section}.{name}",
                        name=str(name),
                        values=values,
                        hard=hard,
                        required=bool(spec.get("required", False)),
                        description=str(spec.get("description", "")).strip(),
                    )
                )
        return out
