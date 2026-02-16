# Contributing to Cosolvent

Thanks for helping build better infrastructure for thin markets.

## Before You Start

1. Read `WHITEPAPER.md` for the product thesis.
2. Open an issue describing the problem, expected behavior, and scope.
3. Keep PRs focused: one change set per PR whenever possible.

## Development Setup

```bash
git clone https://github.com/DeeperPoint/cosolvent-beta.git
cd cosolvent-beta
cp .env.example .env
make setup-up
make up
make wait-api
```

For local (non-Docker) setup, see `docs/getting-started.md`.

## Branch and Commit Style

1. Branch from `main`.
2. Use clear commit messages (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).
3. Include tests with behavior changes.

## Required Quality Gate

Run before opening a PR:

```bash
make lint
make unit
make compile-check
make integration
make e2e
```

If secrets are configured and your change touches AI/provider behavior, also run:

```bash
make live
```

## Generated Files Policy

`marketplace.yaml` is source of truth. Generated outputs include:

- `app/generated/*`
- `generated/manifest.json`
- `openapi/generated_openapi.json`
- `alembic/versions/auto_marketplace_*.py`

Rules:
1. Do not hand-edit generated files.
2. Regenerate via compiler/UI.
3. Only commit generated artifacts when the PR explicitly requires them.

## Pull Request Checklist

1. Problem statement is clear.
2. Backward compatibility impact is documented.
3. Tests were added/updated.
4. Docs were updated where relevant.
5. CI is passing.

## Design and UX Contributions

For onboarding UI work:
1. Keep guided flow non-technical by default.
2. Preserve accessibility (focus states, keyboard access, contrast).
3. Keep visual language aligned to the monochrome design system.

## Need Help?

Use `SUPPORT.md`.
