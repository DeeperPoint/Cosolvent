# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and this project follows SemVer intent while in beta.

## [Unreleased]

### Added

- **AI-assisted registration.** The public registration form (`/register/[type]`) now
  offers three ways to fill it in: by hand, by describing the business in text, or by
  voice. Text/voice run an LLM extraction pass that pre-fills the form fields — nothing
  is submitted automatically; the applicant reviews and edits before submitting.
  Low-confidence guesses are pre-filled but flagged for confirmation.
  - Backend: `POST /api/profiles/{type_slug}/register/extract` — anonymous, stateless,
    per-IP rate-limited. Respects each type's `onboarding.ai_extraction_enabled` flag.
  - Voice uses the browser's Web Speech API (no API key, no new dependency; Chrome/Edge/
    Safari — Firefox falls back to the text box).
  - Field extraction defaults to `openrouter` / `google/gemini-2.0-flash-001` (a cheap,
    JSON-schema-reliable model); override per-use-case via LLM settings.
- Open-source community standards docs:
  - `LICENSE` (MIT)
  - `CONTRIBUTING.md`
  - `CODE_OF_CONDUCT.md`
  - `SECURITY.md`
  - `SUPPORT.md`
- Purpose-driven README rewrite aligned to thin-market whitepaper framing.
- Diagram-based docs to explain onboarding and generation flow.

### Changed

- `pyproject.toml` enriched with package metadata (`license`, `readme`, `authors`, classifiers, project URLs).
