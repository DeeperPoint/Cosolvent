# Security Policy

## Supported Versions

Security fixes are prioritized for the latest `main` branch and the latest tagged release.

## Reporting a Vulnerability

Please do not open public issues for security vulnerabilities.

Use one of these channels:
1. GitHub Security Advisories for this repository (preferred).
2. Private maintainer contact via repository maintainers on GitHub.

Please include:
- affected endpoint/module,
- reproduction steps or proof of concept,
- impact assessment,
- suggested mitigation (if available).

We will acknowledge reports as quickly as possible and share remediation timelines once triaged.

## Security Expectations

- Never commit secrets (`.env`, API keys, tokens, credentials).
- Use least-privilege credentials in local and production environments.
- Keep provider keys optional for local development where possible.
- Treat generated exports as sensitive if they include environment-specific configuration.
