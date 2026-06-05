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

`--enrich` enables an OpenRouter LLM repair pass (needs `OPENROUTER_API_KEY`); without it
the run is fully deterministic and offline.

## Pipeline

```
domain schema ─▶ extract.py ─▶ MarketDefinition ─▶ assemble.py ─▶ draft dict
                  (the pivot)                                          │
                                                                       ▼
   marketplace.yaml ◀── generate.py ◀── validate.py (validate + repair vs MarketplaceConfig)
```

| Module | Role |
|---|---|
| `domain_schema.py` | Load schema; read `participant_roles`, extract `allowed_values`/`examples` vocab |
| `ir.py` | `MarketDefinition` — participant-oriented intermediate representation |
| `extract.py` | **The pivot**: deal-entity schema → 2–3 participant types + profile fields |
| `permissions.py` | Deterministic role-kind → permissions / communication / discovery rules |
| `assemble.py` | `MarketDefinition` → config dict |
| `validate.py` | Validate-repair loop (deterministic repairs first, optional LLM repair) |
| `llm.py` | Pluggable `LLMClient` (OpenRouter impl); stubbable in tests |
| `generate.py` | Orchestration + provenance + clean YAML emission |
| `cli.py` | Argparse entrypoint |

## Notes / known constraints

- **MVP 3-type cap (ROADMAP "Conflict C3").** At most one participant type per role kind,
  so many facilitator sub-roles (broker, shipper, inspector, …) collapse into one
  `facilitator`. The collapse is reported on stdout and on `ParticipantDef.collapsed_subtypes`.
  When C3 is relaxed, only `extract.py` needs to change.
- **Config drift caught:** the committed root `marketplace.yaml` uses `can_search: [list]`,
  but the model declares `can_search: bool`. This generator emits the model-valid `bool`.
- The deterministic baseline projects identity + role-appropriate vocabulary fields. The
  LLM enrichment pass (richer field selection/labels/visibility inference) is the next
  extension point — wire it in `generate.py` before `assemble`.

## Tests

```bash
cd backend && .venv/bin/python -m pytest configgen/tests -v
```

Fully offline (no LLM). Golden test: the real grain schema → a config that both validates
and round-trips through the validator from disk.
