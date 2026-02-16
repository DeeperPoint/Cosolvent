# Support

## Where to Get Help

1. **Questions / usage help**  
   Open a GitHub Discussion or issue with:
   - what you are trying to achieve,
   - what you expected,
   - what happened instead.

2. **Bug reports**  
   Open a GitHub issue and include:
   - environment (`Docker` or local),
   - relevant `make` command,
   - logs/error output,
   - reproduction steps.

3. **Security concerns**  
   Follow `SECURITY.md`.

## Fast Troubleshooting

- Health check: `http://localhost:18000/api/health`
- API logs: `make logs-api`
- Worker logs: `make logs-worker`
- Regeneration drift: `make compile-check`

## Docs

- `README.md`
- `docs/getting-started.md`
- `docs/testing.md`
- `docs/generation.md`
