"""Top-level orchestration: domain schema (+ optional LLM) -> validated marketplace.yaml.

Pipeline:
  1. load domain schema            (CommonContext output)
  2. extract MarketDefinition      (deterministic pivot; extract.py)
  3. [optional] LLM enrichment     (refine fields/labels)
  4. assemble config dict          (assemble.py)
  5. validate + repair             (validate.py — imports the real MarketplaceConfig)
  6. emit YAML
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.core.marketplace_config import MarketplaceConfig

from .assemble import assemble
from .domain_schema import DomainSchema
from .extract import extract_market
from .ir import MarketDefinition
from .llm import LLMClient, make_llm_repair
from .validate import validate_and_repair


@dataclass
class GenerationResult:
    config: MarketplaceConfig
    config_dict: dict[str, Any]
    market: MarketDefinition
    provenance: dict[str, str]   # field name -> source schema path

    def to_yaml(self) -> str:
        return yaml.safe_dump(_drop_nulls(self.config_dict), sort_keys=False, allow_unicode=True, width=100)


def _drop_nulls(value: Any) -> Any:
    """Recursively drop None-valued keys so the emitted YAML omits unused optionals
    (e.g. ``options``/``accepted_types`` on non-select fields) — matching how a
    hand-written marketplace.yaml looks. The result still validates."""
    if isinstance(value, dict):
        return {k: _drop_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_nulls(v) for v in value]
    return value


def _collect_provenance(market: MarketDefinition) -> dict[str, str]:
    prov: dict[str, str] = {}
    for p in market.participants:
        for sec in p.sections:
            for f in sec.fields:
                if f.source:
                    prov[f"{p.slug}.{f.name}"] = f.source
    return prov


def generate_from_schema(
    schema_path: str | Path,
    *,
    name: str | None = None,
    industry: str | None = None,
    llm_client: LLMClient | None = None,
) -> GenerationResult:
    schema = DomainSchema.load(schema_path)
    market = extract_market(schema, name=name, industry=industry)

    draft = assemble(market)

    # Optional LLM enrichment: refine visibility / select-vs-multi / labels before
    # validation. Applied through a whitelist (see enrich.py); validation is the backstop.
    if llm_client is not None:
        from .enrich import enrich_fields

        draft = enrich_fields(llm_client, draft)

    repair = make_llm_repair(llm_client) if llm_client is not None else None
    cfg = validate_and_repair(draft, llm_repair=repair)

    # Use the validated, normalized dict for emission.
    config_dict = cfg.model_dump(mode="json")
    return GenerationResult(
        config=cfg,
        config_dict=config_dict,
        market=market,
        provenance=_collect_provenance(market),
    )
