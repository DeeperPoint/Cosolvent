# Cosolvent Beta

Cosolvent Beta helps teams launch a marketplace backend for thin markets without starting from scratch.

## Why We Built Cosolvent

Most marketplaces fail early for the same reasons:
- the right buyers and suppliers exist, but finding each other is hard,
- trust signals are scattered,
- onboarding is inconsistent,
- teams spend months wiring basic flows before learning if the market works.

We built Cosolvent to shorten that path.

You should be able to go from idea to a usable, policy-aware marketplace runtime in days, not quarters.

## Thin Markets, Simply

A thin market is a market where matches are possible but fragile.

People are willing to trade, but friction blocks outcomes:
- not enough visibility,
- unclear profile quality,
- too much back-and-forth,
- weak trust defaults.

## Where AI Actually Helps

AI is useful here when it reduces operator and user effort:
- better profile understanding,
- better retrieval/discovery,
- faster onboarding assistance,
- clearer communication support.

AI is not used as a magic replacement for your business rules.
Your market logic still comes from explicit configuration and deterministic generation.

## How Cosolvent Helps

Cosolvent gives you a guided system, not a blank framework:

1. Guided setup UI for operators
- Define participant roles, permissions, onboarding rules, communication policy, discovery behavior.

2. Deterministic compile pipeline
- Same config in -> same artifacts out.
- Drift checks tell you when runtime artifacts are stale.

3. Safety by default
- Validation-first setup.
- Managed-zone generation and overwrite rules.
- Auditable config-to-runtime translation.

4. Usable day-to-day workflow
- Edit setup in guided UI.
- Validate.
- Generate.
- Run and iterate.

## Who This Is For

- founders validating a B2B marketplace concept,
- product/ops teams that need a configurable backend quickly,
- engineers who want clear extension points after baseline setup.

## Quick Start

```bash
git clone https://github.com/DeeperPoint/cosolvent-beta.git
cd cosolvent-beta
cp .env.example .env
make setup-up
make onboarding
```

Open: `http://localhost:18080/onboarding`

Then generate and run:

```bash
make compile
make up
make wait-api
```

API docs: `http://localhost:18000/docs`

## Daily Workflow

1. Open onboarding.
2. Update setup decisions.
3. Validate setup.
4. Generate artifacts.
5. Run tests.

Recommended checks:

```bash
make lint
make unit
make compile-check
```

## Notes on Generated Artifacts

Generated artifacts are local build outputs and should not be hand-edited.
Regenerate from config and compiler changes.

## Documentation

Start with `docs/README.md` for a quick map.
