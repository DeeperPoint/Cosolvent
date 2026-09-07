# configgen — Domain schema → `marketplace.yaml` generator

The MarketForge "Domain schema → `marketplace.yaml`" connector (Forge ROADMAP §7).
It turns a CommonContext domain schema (`<vertical>_schema.yaml`) into a Cosolvent
`marketplace.yaml`, guaranteed to validate against the real `MarketplaceConfig` model.

## Why it's reliable

The generator **imports Cosolvent's `app.core.marketplace_config.MarketplaceConfig`** and
uses it as an acceptance oracle: it never emits a config that doesn't deserialize and pass
`cross_validate`. So "valid" is not approximated — it's the actual runtime contract. (It
also passes the compiler front-end `normalize_to_ir`, i.e. the output compiles.)

## Usage

```bash
cd backend

# Standalone
.venv/bin/python -m configgen \
    --domain-schema ../../CommonContext/schemas/grain_trade_schema.yaml \
    --name "Prairie Grain Trade" -o marketplace.yaml --provenance

# Or as a Cosolvent CLI subcommand
.venv/bin/python -m cli generate-config \
    --domain-schema ../../CommonContext/schemas/grain_trade_schema.yaml \
    -o marketplace.yaml
```

The CLI (`python -m configgen`) always requires `OPENROUTER_API_KEY` — enrichment and
repair are mandatory there, both running on Claude via OpenRouter (`--model` or
`OPENROUTER_MODEL` to override). The fully deterministic, no-LLM path is available at
the library level — call `generate_from_schema(schema_path)` with no `llm_client` — and
is how `configgen/tests` runs offline.

## Pipeline

```
domain schema ─▶ extract.py ─▶ MarketDefinition ─▶ assemble.py ─▶ draft dict
                  (the pivot)                                          │
                                                                       ▼
                                                          enrich.py (LLM, optional:
                                                          visibility / label / select
                                                          type — whitelisted fields only)
                                                                       │
                                                                       ▼
   marketplace.yaml ◀── generate.py ◀── validate.py (validate + repair vs MarketplaceConfig)
```

| Module | Role |
|---|---|
| `domain_schema.py` | Load schema; read `participant_roles`, extract `allowed_values`/`examples` vocab |
| `ir.py` | `MarketDefinition` — participant-oriented intermediate representation |
| `extract.py` | **The pivot**: deal-entity schema → participant types + profile fields |
| `permissions.py` | Deterministic role-kind → permissions / communication / discovery rules |
| `assemble.py` | `MarketDefinition` → config dict |
| `validate.py` | Validate-repair loop (deterministic repairs first, optional LLM repair) |
| `llm.py` | Pluggable `LLMClient` (OpenRouter impl); stubbable in tests |
| `enrich.py` | LLM enrichment pass — refines visibility/label/select-vs-multi through a strict whitelist; never touches names, options, slugs, or structure |
| `generate.py` | Orchestration + provenance + clean YAML emission |
| `cli.py` | Argparse entrypoint |

## Notes / known constraints

- **3-type cap resolved (ROADMAP "Conflict C3").** Supply/demand still get one participant
  type each, but facilitator subtypes (broker, shipper, inspector, …) now expand into one
  participant type *per subtype* — up to `MAX_PARTICIPANT_TYPES` (`app.core.marketplace_config`,
  currently 8) minus however many non-facilitator types are in play. A schema with more
  subtypes than that remaining budget still collapses into one generic `facilitator` type
  (reported on stdout and on `ParticipantDef.collapsed_subtypes`) — now the overflow case,
  not the default. See `extract.py::_facilitator_participants` and
  `configgen/tests/test_facilitator_expansion.py`.
- **Config drift caught:** the committed root `marketplace.yaml` uses `can_search: [list]`,
  but the model declares `can_search: bool`. This generator emits the model-valid `bool`.
- **LLM enrichment is wired in.** The deterministic baseline projects identity +
  role-appropriate vocabulary fields; when `generate_from_schema` is given an
  `llm_client`, it runs `enrich.py` on the assembled draft before validation to refine
  field visibility, labels, and select-vs-multi choices. Applied through a whitelist
  (`enrich.py`), so validation stays the backstop either way. See
  `test_generate_from_schema_applies_enrichment_when_llm_client_given` in
  `configgen/tests/test_grain.py` for the wiring itself, and
  `test_enrichment_applies_whitelisted_adjustments_only` for the whitelist.

## Tests

```bash
cd backend && .venv/bin/python -m pytest configgen/tests -v
```

Fully offline (no LLM). Golden test: the real grain schema → a config that both validates
and round-trips through the validator from disk.
