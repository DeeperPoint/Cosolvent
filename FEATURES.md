<!--Copyright (c) 2026 Mustafa Uzumeri. All rights reserved.-->

# Cosolvent — Product Feature Sheet

> **An open-source, headless marketplace engine for launching marketplace platforms in thin markets.** Includes a full sponsor admin dashboard; the participant-facing frontend is yours to build.

| Icon | Meaning |
|:---:|---|
| ✅ | **Implemented** — working in the current codebase |
| 🔜 | **Planned** — on the development roadmap, not yet built |

---

## Configuration & Deployment

| | Feature | Description |
|:---:|---|---|
| ✅ | **YAML-Driven Marketplace Definition** | Define participant types, profile schemas, permissions, onboarding rules, communication policies, and discovery settings in a single `marketplace.yaml` file. No code changes required for new market verticals. |
| ✅ | **Deterministic Compiler Pipeline** | YAML → normalize → hash → render → write → manifest. Reproducible artifact generation with spec hashing and drift detection (`compile --check`). |
| ✅ | **Built-In Presets** | Three starter configurations to accelerate initial setup. |
| ✅ | **7-Step Setup Wizard** | Interactive CLI onboarding walks operators through marketplace configuration decisions. |
| ✅ | **Browser-Based Setup Panel** | Visual configuration UI with presets, real-time validation, and live YAML preview. |
| ✅ | **Docker Compose Deployment** | Single-command launch of the full stack: API server, PostgreSQL + pgvector, Redis, ARQ background workers. |
| ✅ | **Health Checks & Graceful Shutdown** | Production-ready lifecycle management. Redis-optional startup ensures resilience when queue infrastructure is unavailable. |
| 🔜 | **Admin-Triggered Recompilation** | Admin UI modifies marketplace config and triggers recompile + hot-reload without developer involvement. |
| 🔜 | **AI-Assisted Market Configuration** | AI assistant in admin panel generates config suggestions from conversational market description. |
| 🔜 | **Multi-Tenancy** | Tenant isolation or vertical scoping for hosting multiple marketplaces on a single deployment. |

---

## Profile Infrastructure

| | Feature | Description |
|:---:|---|---|
| ✅ | **Dynamic Profile Schemas** | Runtime Pydantic models generated from marketplace config via `pydantic.create_model()`. No hard-coded entity types — the schema follows the config. |
| ✅ | **Config-Driven Participant Roles** | Supply, demand, and facilitator roles with per-type permission sets: listing, search, conversation initiation, private asset sharing, onboarding gates, approval requirements. |
| ✅ | **Three-Tier Field Visibility** | Every profile field is tagged `public`, `protected`, or `private`. The visibility engine enforces access by viewer authentication status and ownership context. |
| ✅ | **Profile Completeness Scoring** | Automatic calculation of profile completeness against configurable thresholds — used to gate onboarding and marketplace access. |
| ✅ | **Configurable Onboarding Flows** | Per-participant-type onboarding: manual vs. auto approval, document upload requirements, AI extraction toggles, welcome emails, completeness thresholds. |
| 🔜 | **Gallery / Matching Profile Separation** | Split profiles into a curated gallery layer (for browsing) and a richer matching layer (budget ranges, capacity constraints, inferred preferences) used by AI but never displayed to other participants. |
| 🔜 | **Gallery Profile Editor** | UI for participants to review, edit, and approve their public-facing gallery profile before it goes live. |
| 🔜 | **Expanded Participant Type Limit** | Relax the current 3-participant-type cap to support marketplaces with multiple facilitator subtypes (customs broker, shipper, inspector, trade finance, insurance). |
| 🔜 | **Group / Cooperative Participant Type** | Groups of small producers participate as a single marketplace entity with aggregated profiles, member data collection, and designated managers. |

---

## AI & Semantic Search

| | Feature | Description |
|:---:|---|---|
| ✅ | **AI-Powered Document Extraction** | LLM reads uploaded documents and extracts structured profile fields automatically — reducing manual data entry for participants. |
| ✅ | **AI Profile Summary Generation** | LLM generates natural-language profile summaries from structured field data. |
| ✅ | **Semantic Vector Search** | pgvector cosine-distance search over participant profile embeddings. Metadata filtering, profile field filtering, and configurable similarity thresholds. |
| ✅ | **Hybrid & RAG Search Modes** | Two retrieval modes — `hybrid` (vector + keyword) and `rag_strict` (vector-only with strict grounding). Configurable failure behaviour. |
| ✅ | **Multi-Provider AI Abstraction** | Provider-agnostic LLM and embedding layer supporting OpenAI, OpenRouter, and Google Gemini. Dynamic model resolution from database configuration. |
| ✅ | **Dynamic Model Fetching** | Live model list retrieval with TTL cache for all supported providers. |
| ✅ | **Prompt Management System** | Database-backed custom prompts with fallback defaults. Four built-in intents: `rag_query`, `follow_up`, `profile_generation`, `document_extraction`. |
| ✅ | **Document Processing Pipeline** | Text chunking (1000 chars / 200 overlap), embedding generation, and indexing to vector store via background workers. |
| 🔜 | **VLM Integration** | Image-based document extraction for certificates, invoices, product photos, and spec sheets via Vision Language Models. |
| 🔜 | **Speech-to-Text Integration** | Voice input via Whisper or equivalent, with multilingual support. |
| 🔜 | **Natural Language Listing Creation** | Voice or text descriptions converted to structured marketplace listings automatically. |
| 🔜 | **Dual Embedding Pipeline** | Separate embedding spaces for gallery search (public data only) and deep matching (private + public signals). |
| 🔜 | **Task-Level Model Routing** | Different AI models assigned to different pipeline tasks (extraction, matching, generation) with fallback chains. |
| 🔜 | **Knowledge Slot (Reference Library)** | Sponsor-curated domain knowledge library — separate from participant documents — with vertical-specific metadata, curation workflow, and domain Q&A integration. |
| 🔜 | **Additional AI Providers** | Anthropic, HuggingFace, Ollama, and custom REST endpoint support. |

---

## Matching & Deal Engine

| | Feature | Description |
|:---:|---|---|
| ✅ | **Participant Discovery** | Config-driven search: searchable types, filter fields, anonymous vs. authenticated result visibility, similarity threshold. |
| 🔜 | **Bidirectional Matching** | Mutual preference matching that considers both parties' profiles, not just one-directional search. |
| 🔜 | **Match Rationale Generation** | LLM-generated "why this match" explanations that respect privacy boundaries — never leaking private signals. |
| 🔜 | **Generative Preference Elicitation** | Conversational discovery of requirements replacing free-text search — the system asks questions to understand what you need. |
| 🔜 | **Three Search Modes** | Gallery search (public profiles), participant-to-participant match (deep, private signals), and deal-to-facilitator search (deal requirements → service providers). |
| 🔜 | **Deal Data Model** | Structured deal entity linking principals, facilitators, role slots (needed / searching / proposed / confirmed), product/service, route, volume, timeline, and quality requirements. |
| 🔜 | **Deal-Triggered Facilitator Search** | When a buyer-seller match progresses to deal structuring, the system automatically searches for facilitators whose capabilities match the deal's requirements. |
| 🔜 | **Handoff Artifact** | The platform's primary deliverable — a structured output assembled from profiles, matching signals, conversation context, shared documents, facilitator recommendations, and regulatory flags. Admin-configurable template per deployment. |
| 🔜 | **Asynchronous Brokerage Agents** | AI agents configured per participant with negotiation parameters, authority levels, and persona. Multi-turn, state-persisted conversations across days with human escalation. |
| 🔜 | **Deal Progression Workflow** | Inquiry → qualification → negotiation → deal structuring → human approval → Handoff Artifact. |
| 🔜 | **Dynamic Pricing** | Asking prices, transaction history, fair-value estimation from comparables, and confidence-banded price guidance in match results. |
| 🔜 | **Geographic & Temporal Matching** | Geolocation-aware search with logistics cost estimation, production/availability window overlap scoring, and configurable shipping radii. |
| 🔜 | **Anticipatory Matching** | Proactive notifications when new listings match a participant's inferred or stated needs — the system reaches out, not just responds. |

---

## Communication

| | Feature | Description |
|:---:|---|---|
| ✅ | **Conversation Lifecycle Management** | Create, accept, reject, and close conversations with full state tracking. |
| ✅ | **Messaging** | Send, edit, and delete messages within conversation contexts. |
| ✅ | **Real-Time WebSocket Support** | Live message delivery via WebSocket connections. |
| ✅ | **Asset Sharing** | Participants can share files within conversation threads. |
| ✅ | **Config-Driven Communication Rules** | Conversation initiation rules defined per participant-type pair in marketplace config — who can contact whom, and whether approval is required. |
| ✅ | **Permission-Gated Initiation** | The permission engine validates conversation rights against onboarding status and role configuration before allowing contact. |
| 🔜 | **Match-Scoped Messaging** | AI creates a scoped channel for introductions when a match is made — conversation context tied to the match. |
| 🔜 | **Deal-Scoped Messaging** | Multi-party communication within a deal context — all principals and facilitators in one thread. |
| 🔜 | **Progressive Trust Gating** | Communication channels unlock progressively as trust stages advance — anonymous browsing → guided introduction → structured exchange → protected transaction. |
| 🔜 | **Notification Service Expansion** | Email, SMS, and push notification delivery beyond in-app messaging. |
| 🔜 | **WhatsApp / SMS / USSD Interface** | Low-bandwidth channel access for participants in regions with limited internet connectivity. |

---

## Trust & Verification

| | Feature | Description |
|:---:|---|---|
| ✅ | **Admin Approval Workflow** | Binary trust gate — admin manually approves or rejects participant applications. |
| 🔜 | **Verification Pipeline** | Auto-analyze uploaded documents for consistency, cross-reference external data, and assign verification confidence scores. |
| 🔜 | **Reputation System** | Track transaction outcomes, response times, dispute rates, and counterparty ratings to build participant trust profiles. |
| 🔜 | **Progressive Trust Stages** | Six-stage trust ladder: anonymous browsing → verified profile → guided introduction → structured information exchange → protected transaction → post-transaction evaluation. |
| 🔜 | **Transparent Matching** | Surface AI reasoning to participants while respecting privacy boundaries — explain *why* a match was recommended without leaking private data. |
| 🔜 | **Dispute Resolution Pipeline** | Claims, evidence chains, AI triage for minor issues, escalation for complex cases, and predictive risk scoring on in-progress deals. |
| 🔜 | **Zero-Knowledge Credential Verification** | W3C Verifiable Credentials with BBS+ selective disclosure — participants prove claims without transmitting underlying documents. For regulated sectors and cross-border transactions. |

---

## Admin & Operator Tools

| | Feature | Description |
|:---:|---|---|
| ✅ | **Admin Dashboard** | Aggregate marketplace statistics and operational overview. |
| ✅ | **User Management** | View, search, and manage participant accounts. |
| ✅ | **Application Approval / Rejection** | Manual review workflow for participant onboarding applications. |
| ✅ | **Conversation Oversight** | Admin visibility into active marketplace communication. |
| ✅ | **LLM Settings Management** | Runtime configuration of AI provider, model selection, and generation parameters without redeployment. |
| ✅ | **Prompt Management** | Create, edit, and version custom prompts via admin API. |
| ✅ | **Document Management** | Oversight of uploaded participant documents. |
| ✅ | **FAQ Management** | CRUD operations for marketplace FAQ content. |
| 🔜 | **UI Customization Layers** | Configurable terminology mapping, LLM-assisted locale/language file generation, and CSS theme configuration per deployment. |
| 🔜 | **LLM Call Observability** | Per-call logging of model, token counts, latency, cost estimate, service name, and success/failure status. |
| 🔜 | **Structured Logging** | JSON-formatted logs, environment-variable log levels, and request correlation IDs. |
| 🔜 | **Privacy Audit Log** | Track document privacy changes for compliance reporting. |
| 🔜 | **Scheduled Job Runner** | Reputation recalculation, preference evolution analysis, predictive risk scoring on a configurable schedule. |

---

## File Management

| | Feature | Description |
|:---:|---|---|
| ✅ | **S3 Storage Backend** | All participant files stored in Amazon S3. |
| ✅ | **Public / Private File Privacy** | Binary privacy classification with enforcement at the API layer. |
| ✅ | **Presigned URL Access** | Secure, time-limited download URLs for private files. |
| ✅ | **Upload Size Limits** | Configurable file size cap (default 25 MB). |
| 🔜 | **Multi-Level File Privacy** | Expand from binary to five levels: `public`, `gallery`, `match-only`, `ai-only`, `private`. |
| 🔜 | **Privacy-Aware Extraction Routing** | Extracted data routed to the correct profile layer (gallery vs. matching) based on document privacy settings. |

---

## Developer & Operator Experience

| | Feature | Description |
|:---:|---|---|
| ✅ | **Makefile Workflow** | Single-command operations: `make setup-up`, `make compile`, `make up`, `make lint`, `make unit`, `make compile-check`. |
| ✅ | **OpenAPI Documentation** | Auto-generated interactive API docs at `/docs`. |
| ✅ | **Drift Detection** | `compile --check` verifies generated artifacts match current config — catches hand-edits and config/code divergence. |
| ✅ | **Managed Output Zones** | Compiler writes to designated directories only. Clear separation of hand-written and generated code. |
| ✅ | **36+ Unit Tests** | Coverage across config, compiler, permissions, visibility, schemas, discovery, profiles, communication, files, auth, database, Redis, and queue. |
| ✅ | **Alembic Migrations** | Database schema versioning via Alembic. |
| ✅ | **Background Job Processing** | ARQ worker pool for asynchronous document processing, embedding generation, and other long-running tasks. |
| 🔜 | **MCP Client Integration** | Model Context Protocol client for external data source and tool connectivity. |
| 🔜 | **API Gateway** | Rate limiting, API keys, and usage tracking. |
| 🔜 | **Vector Database Scaling** | HNSW indexing and performance monitoring for large participant sets. |

---

## Security & Privacy

| | Feature | Description |
|:---:|---|---|
| ✅ | **Authentication System** | User registration, login, and session management. |
| ✅ | **Three-Tier Data Visibility** | Enforced at the API layer — unauthenticated users see `public` only; authenticated users see `public` + `protected`; owners see all. |
| ✅ | **Per-Field Privacy Control** | Each profile field carries its own visibility setting, defined in config and enforced at query time. |
| ✅ | **Permission Engine** | Config-driven checks on every protected action: search, listing, conversation initiation, asset sharing. |
| ✅ | **Onboarding Gates** | Participants must complete onboarding (and receive approval, if configured) before accessing marketplace features. |
| 🔜 | **Encryption at Rest** | Encryption for confidential matching profile data in the database. |
| 🔜 | **Confidential Matching Pipeline** | AI evaluates fit using both gallery and matching profiles, revealing only *that* a match exists — never the underlying sensitive data. |

---

## Architecture Summary

| Component | Technology |
|---|---|
| **Language** | Python 3.11+ |
| **API Framework** | FastAPI |
| **Database** | PostgreSQL + pgvector |
| **Cache / Queue** | Redis + ARQ |
| **Object Storage** | Amazon S3 |
| **Containerisation** | Docker / Docker Compose |
| **AI Providers** | OpenAI · OpenRouter · Google Gemini |
| **Schema Validation** | Pydantic v2 |
| **Migrations** | Alembic |
| **License** | Open Source (see LICENSE) |

---

## Scope Boundaries

Cosolvent is deliberately **unopinionated** about the specific business conducted over it. It provides the matching engine; it defers the following to vertical-specific implementations:

- **Frontend interfaces** — all user-facing web, mobile, and conversational UIs
- **Domain ontology** — the specific rules, criteria, and taxonomies defined by the marketplace sponsor
- **Trust & verification protocols** — credential validation, dispute mediation, and real-world safety
- **Business add-ons** — payments, escrow, monetisation, logistics, and digital twin simulation

This boundary keeps Cosolvent lightweight, generalizable, and scalable. The market sponsor retains full ownership of UX, revenue generation, and domain-specific liability.

---

## Ecosystem

| Project | Role |
|---|---|
| **MarketForge** | Market configuration and deployment orchestration |
| **CommonContext** | AI-curated reference library for domain knowledge |
| **ClientSynth** | Synthetic participant generation for testing and demos |
