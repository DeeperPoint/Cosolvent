<!-- Copyright © 2026 Mustafa Uzumeri. All rights reserved. -->

# Cosolvent Roadmap

> **Purpose:** An open-source headless marketplace engine for thin market automation — translating market engineering theory into deployable infrastructure.
>
> **Date:** March 6, 2026
> **Author:** Mustafa Uzumeri

---

## Executive Summary

Cosolvent is an open-source headless marketplace engine for building AI-assisted marketplace platforms designed for thin markets — markets where transactions are infrequent, matching is difficult, and beneficial exchanges fail to occur despite willing participants on both sides.

The engine already provides working implementations of several foundational capabilities. The remaining work extends this foundation across three categories:

| Category | Description |
| --- | --- |
| **Already built** | Foundation Cosolvent has that the roadmap builds on |
| **Extension work** | Features to add on the existing foundation |
| **Future phases** | Deeper capabilities planned for later stages |

**Estimated time to demo-ready state:** 14–20 weeks from start of active development, reflecting the strong foundation already in place.

---

## 1. Foundation Already in Place

Cosolvent provides working implementations of the following. No rebuild needed — these are the platform base.

### 1.1 YAML-Driven Marketplace Configuration ✅

Marketplace structure is defined in a configuration file, compiled through a deterministic pipeline, and validated with drift detection. Three built-in presets accelerate deployment.

### 1.2 Dynamic Profile Schemas ✅

Profile data structures are defined per marketplace deployment, with runtime validation and completeness calculation.

### 1.3 Three-Tier Visibility ✅

Field-level visibility enforced as **public** / **protected** / **private**, based on viewer authentication status and data ownership.

### 1.4 Facilitator Participant Type ✅

Three participant roles supported: **supply**, **demand**, and **facilitator** — the full multilateral structure required for complex deal assembly.

### 1.5 AI-Assisted Onboarding ✅

Structured profile fields extracted from documents via LLM. AI-generated profile summaries. Configurable per participant type.

### 1.6 Vector Search ✅

Cosine-distance semantic search with metadata filtering. Two retrieval modes: hybrid (semantic + metadata) and strict (retrieval-augmented only).

### 1.7 Admin Oversight ✅

Dashboard with platform statistics, user management, application approval, conversation oversight, LLM settings, prompt management, document management, and FAQ management.

### 1.8 Prompt Management ✅

Template system with database-backed custom prompts and fallback defaults. Prompts for query, follow-up, profile generation, and document extraction — all editable by administrators.

### 1.9 Communication System ✅

Full conversation lifecycle (create, accept, reject, close), message send/edit/delete, real-time updates, asset sharing, and configuration-driven communication rules.

### 1.10 Permission Engine ✅

Participant permissions checked against marketplace configuration. Conversation initiation rights validated. Onboarding requirements enforced.

### 1.11 Document Processing Pipeline ✅

Text-based document ingestion with chunking, embedding, and indexing. Background processing. Voice and image input planned for a future phase.

### 1.12 File Management, Notifications, Testing, Deployment, CLI ✅

- **Files:** Cloud storage backend, public/private privacy, 25MB limit
- **Notifications:** Notification plumbing in place for future expansion
- **Tests:** Full unit test coverage across core modules
- **Deployment:** Docker Compose, health checks, graceful shutdown
- **CLI:** Seven-step setup wizard with browser-based configuration panel, presets, and YAML preview

---

## 2. Three-Layer Information Architecture — Extensions

### What's built

Three-tier field visibility and binary file privacy.

### What's planned

#### 2.1 — Separate Gallery Profile from Matching Profile

Add a gallery profile (curated, user-approved, for browsing) and a matching profile (richer data used by AI but never displayed). Profile visibility layers extended accordingly.

#### 2.2 — Expand Document Privacy Levels

Expand file privacy from binary to multi-level: public, gallery, match-only, AI-only, private.

#### 2.3 — Privacy-Aware Extraction Routing

Route AI-extracted data to the correct profile layer based on document privacy settings. Re-route when privacy level changes.

#### 2.4 — Dual Embedding Pipeline

Gallery search uses gallery-only embeddings. Matching search uses richer embeddings incorporating private profile signals.

#### 2.5 — Gallery Profile Editor

User interface for reviewing, editing, and approving the public gallery profile before it becomes visible.

---

## 3. Multilateral Marketplace — Extensions

### What's built

Three participant roles, configuration-driven participant types, conversation system with full lifecycle management.

### What's planned

#### 3.1 — Deal Entity

A Deal data model with: principals involved, product or service transacted, route, volume, value, timeline, quality requirements, and role slots for facilitator roles (status: needed, searching, proposed, confirmed, not-needed).

#### 3.2 — Deal-Triggered Facilitator Search

When a buyer-seller match progresses to deal structuring, analyze deal requirements and search for facilitators whose capability profiles match — a second matching pattern distinct from participant-to-participant discovery.

#### 3.3 — Deal Assembly Interface

Deal view showing parameters, role slot status, AI-recommended facilitators, and attached facilitators.

#### 3.4 — Facilitator Dashboard

Deal feed, active engagements, and capacity management for facilitator participants.

#### 3.5 — Communication Extensions

- Match-scoped messaging — AI creates a scoped introduction channel
- Deal-scoped messaging — multi-party communication within a deal context
- Progressive trust gating — channels unlock as trust stages advance

#### 3.6 — Handoff Artifact

The platform's primary deliverable — a structured output assembled from profiles, matching signals, conversation context, shared documents, facilitator recommendations, and regulatory flags. Template is admin-configurable per marketplace deployment.

---

## 4. Semantic Matching Engine — Extensions

### What's built

Semantic vector search with metadata filtering and two retrieval modes.

### What's planned

- **4.1 — Bidirectional matching** — mutual preference matching considering both parties' profiles simultaneously
- **4.2 — Multi-signal embedding enrichment** — structured templates blending multiple profile signals, different templates per participant type
- **4.3 — Match rationale generation** — LLM-generated "why this match" explanations that respect privacy boundaries
- **4.4 — Generative preference elicitation** — conversational discovery of requirements replacing free-text search
- **4.5 — Three search modes** — gallery search (public profiles), participant-to-participant match search (deep, private signals), deal-to-facilitator search (deal requirements → service providers)

---

## 5. Trusted Intermediary Protocol

### What's built

Nothing yet. Participants communicate directly.

### What's planned

Implemented through the three-layer architecture:

- **Confidential matching pipeline** — LLM reads from both gallery and matching profiles, evaluates fit, reveals only *that* a match exists without exposing underlying sensitive data
- **Structured disclosure gates** — parties progressively share information by elevating document privacy levels
- **Privacy-respecting rationale** — match explanations designed so they cannot leak private signals

---

## 6. Multimodal Input Pipeline — Extensions

### What's built

Text-based document processing. No voice or image input yet.

### What's planned

- **6.1 — Image-based document extraction** — certificates, invoices, product photos processed via vision-language models
- **6.2 — Voice input** — multilingual speech-to-text transcription
- **6.3 — Natural language listing creation** — voice or text input converted to structured marketplace listings
- **6.4 — Privacy-aware extraction routing** — multimodal extraction connected to the three-layer privacy model

---

## 7. Asynchronous Brokerage Agents

### What's built

Nothing yet. Human-to-human conversation only.

### What's planned

- **User Agent entity** — each participant configures an AI agent with negotiation parameters, authority levels, persona, and tool access
- **Asynchronous conversation engine** — multi-turn, state-persisted across days, time-zone-aware, with human escalation
- **Deal progression workflow** — inquiry → qualification → negotiation → deal structuring → human approval → Handoff Artifact
- **Notification integration** — leverages existing notification plumbing

---

## 8. Memory and Context Management

### What's built

Basic conversation history in RAG chat threads. No per-user preference memory, no interaction logging, no anticipatory matching.

### What's planned

- **User interaction log** — search queries, match views, rejections, conversation turns
- **Preference evolution analysis** — LLM-driven pattern detection over interaction history
- **Anticipatory matching** — proactive notifications when new listings match inferred needs
- **Deal outcome data** — outcomes recorded for completed and failed transactions
- **Institutional memory** — interaction knowledge persists across participant turnover

---

## 9. Trust Gradation Framework — Extensions

### What's built

Binary trust: admin approves or rejects applications. No graduated model, verification, or reputation tracking.

### What's planned

- **9.1 — Verification pipeline** — auto-analyze documents for consistency, cross-reference external data, assign verification confidence scores
- **9.2 — Reputation system** — track transaction outcomes, response times, dispute rates, counterparty ratings
- **9.3 — Progressive trust stages:**
  1. Anonymous browsing → public gallery only
  2. Verified profile → AI begins using private-layer documents
  3. Guided introduction → AI-mediated contact; gallery profiles shared
  4. Structured information exchange → selective document disclosure
  5. Protected transaction → escrow / insurance / dispute resolution
  6. Post-transaction evaluation → bidirectional ratings
- **9.4 — Transparent matching** — AI reasoning surfaced to participants while respecting privacy boundaries
- **9.5 — Zero-Knowledge Credential Verification (future research)** — W3C Verifiable Credentials with BBS+ selective disclosure, enabling cryptographic proof of participant attributes at the match-introduction boundary without transmitting underlying documents. Gated behind Phase 2 trust infrastructure (§9.1–§9.3) and frontend (C5).

---

## 10. Dynamic Pricing

### What's built

Nothing. No pricing concepts in the data model.

### What's planned

- **Pricing fields** — asking prices, ranges, currency, unit, and conditions on listings
- **Transaction history model** — completed deals with actual prices, quality attributes, and ratings
- **Fair-value estimation service** — comparable analysis with confidence-banded estimates
- **Pricing in match results** — fair-value estimates alongside match recommendations

---

## 11. Dispute Resolution

### What's built

Nothing.

### What's planned

- **Disputes data model** — claims, evidence, and descriptions
- **AI triage** — classify disputes, suggest resolutions for minor issues, escalate complex cases
- **Predictive risk scoring** — flag high-risk in-progress deals before disputes occur

---

## 12. User Aggregation & Cooperatives

### What's built

Nothing. Participants are individuals only.

### What's planned — three implementation tiers

**Tier 1 — Group as marketplace participant:** A group participant type with membership list and designated manager. The group participates in matching as a single entity.

**Tier 2 — Member-aware aggregation:** Members submit data via low-bandwidth channels (SMS, WhatsApp, field agent). Group profiles computed from aggregated member data, with supply schedules and order allocation tracking.

**Tier 3 — Cooperative management:** Revenue distribution, governance, seasonal planning, and certification management for formal cooperative structures.

---

## 13. Psychological Framing & Personalization

### What's built

Nothing. All users see the same content presentation.

### What's planned

- Behavioural analytics tracking for interaction patterns
- Psychographic classification from user behaviour
- Dynamic message framing in chatbot responses, match notifications, and listing displays

---

## 14. Proactive Outreach

### What's built

Nothing. Entirely passive — users must initiate searches.

### What's planned

- **Proactive matching notifications** — alert users when new listings match their needs
- **Outreach generation** — LLM-crafted personalised messages explaining match relevance
- **External signal monitoring** (future) — procurement feeds and market signals to identify potential participants

---

## 15. Geographic & Temporal Distance

### What's built

Profile schemas support a location field type. No geo-aware search, distance calculation, or temporal matching.

### What's planned

- **Geolocation data** — latitude/longitude, logistics cost estimation, and distance filtering
- **Temporal availability models** — production and availability windows on listings, desired delivery windows for buyers
- **Temporal matching** — supply and demand window overlap scoring
- **Time-zone-aware communication** for brokerage agents
- **Economic shipping radii** as configurable parameters per product category

---

## 16. Framework Generalization — Extensions

### What's built

YAML-driven configuration, dynamic schemas, deterministic compiler, prompt management, admin API, and setup wizard.

### What's planned

#### 16.1 — Multi-Provider AI Abstraction

Currently hardcoded to a single AI provider. Planned:

- Provider-agnostic interface supporting multiple AI services
- Task-level routing — different models for different tasks
- Prompt-to-model binding — prompts specify preferred model
- Fallback chains — ordered fallback lists per service

#### 16.2 — Knowledge Slot (Reference Library)

A separate, sponsor-curated domain knowledge store distinct from participant-uploaded documents:

- Reference documents stored and retrieved independently from participant files
- Vertical-specific metadata schema — tag vocabulary defined per marketplace deployment
- Document curation workflow — admin uploads, tags, describes, and versions documents
- Metadata-filtered semantic search — pre-filter by metadata, then rank by relevance
- User-context scoping — participant metadata injected as implicit retrieval filters
- Domain Q&A integration — chatbot supports "domain knowledge" mode with cited answers

#### 16.3 — UI Customization Layers

- **Terminology** — mapping framework concepts to vertical-specific names
- **Language and locale** — LLM-assisted locale file generation; runtime translation for dynamic content
- **Visual branding** — theme configuration for sponsor deployments

#### 16.4 — AI-Assisted Market Configuration

AI assistant in the admin panel that generates configuration suggestions from a conversational market description.

#### 16.5 — MCP Client Integration

External data source and tool connectivity via the Model Context Protocol.

---

## 17. Infrastructure & Operations — Extensions

### What's built

Docker Compose deployment, background job workers, database with vector search, object storage, health checks, and graceful shutdown.

### What's planned

- **Structured logging** — JSON-formatted logs with request correlation IDs and environment-variable log levels
- **AI call observability** — model, token counts, latency, cost estimate, and success/failure tracked per call
- **Notification service expansion** — email, SMS, and push notifications
- **Scheduled job runner** — reputation recalculation, preference evolution analysis, predictive risk scoring
- **Vector database scaling** — optimised indexing and performance monitoring
- **Multi-tenancy** — tenant isolation or vertical scoping for multi-deployment instances
- **API gateway** — rate limiting, API keys, and usage tracking
- **Encryption at rest** — for confidential matching profile data
- **Privacy audit log** — track document privacy changes for compliance

---

## 18. Implementation Phases

### Phase 0 — Observability & Hygiene
*No dependencies. Start immediately. ~1 week.*

- Structured logging with JSON formatter and configurable log levels
- Request correlation IDs
- AI call observability (model, tokens, latency, cost per call)
- Privacy audit log for document privacy changes

### Phase 1 — Three-Layer Architecture & Multilateral Foundation
*Builds on existing profile and visibility infrastructure. 4–6 weeks.*

- Gallery / matching profile separation
- Expanded multi-level file privacy
- Gallery profile editor interface
- Privacy-aware extraction routing
- Dual embedding pipeline (gallery + matching)
- Bidirectional matching
- Match rationale generation
- Deal data model with role slots
- Deal-triggered facilitator search
- Handoff Artifact generator (admin-configurable template)

### Phase 2 — Trust, Verification & Provider Abstraction
*3–5 weeks.*

- Participant verification pipeline
- Reputation and trust score model
- Progressive trust stages with disclosure gating
- Transparent matching with privacy-respecting AI reasoning
- Multi-provider AI abstraction
- Prompt-to-model binding and fallback chains

### Track A — Marketplace Depth
*After Phase 2. Deepens platform capability for facilitating deals.*

**A1 — Deals, Agents & Memory**
- User interaction logging
- Preference evolution analysis
- Anticipatory matching notifications
- Match-scoped and deal-scoped communication channels
- User Agent entity and configuration
- Asynchronous conversation engine
- Deal progression workflow → Handoff Artifact
- Notification service expansion (email, SMS, push)
- ZKP credential verification research spike (§9.5)

**A2 — Pricing, Aggregation & Disputes**
- Transaction history data model
- Fair-value estimation service
- Pricing in match results and Handoff Artifact
- Collective Participant Tier 1 (group as participant)
- Collective Participant Tier 2 (data aggregation)
- Dispute data model and AI triage
- Predictive risk scoring

### Track B — Platform Breadth
*After Phase 2. Extends the platform to more markets and participants.*

**B1 — Input, Framework & Knowledge**
- Image-based document extraction (vision-language model)
- Voice input (speech-to-text)
- Natural language listing creation
- Knowledge Slot reference library
- Metadata-filtered vector search for reference documents
- UI customization layer (terminology, locale, theme)
- MCP client integration
- Market Physics Scorecard model

**B2 — ClientSynth, Digital Twins & Global Scale**
- Cosolvent ↔ ClientSynth API contract (synthetic participant integration for testing and demonstration)
- Synthetic mode with clearly labelled synthetic participants
- Digital Twin simulation environment
- Geolocation and logistics estimation
- Regulatory context module
- WhatsApp / SMS / low-bandwidth interface layer
- Multi-tenancy

### Critical Path

```
Phase 0 (hygiene — ~1 week)
    │
Phase 1 (three-layer + deals — 4–6 weeks)
    │
Phase 2 (trust + provider abstraction — 3–5 weeks)
    │
    ├────────────────────────┐
    ▼                        ▼
Track A: A1 → A2           Track B: B1 → B2
(Deals, Handoff,           (Multimodal, Knowledge,
 Pricing, Disputes)         Framework, ClientSynth)
```

**Estimated calendar time to demo-ready state:** Phase 0 + Phase 1 + Phase 2 + max(A1, B1) = **14–20 weeks**

---

## Cross-Cutting Design Principles

These principles from the thin market framework guide implementation across all phases.

### Why thin markets are different

1. **Structural desire must exist.** AI can accelerate discovery but cannot create demand that does not exist.
2. **Test with thin-market dynamics.** Few participants, infrequent transactions, high stakes per transaction.
3. **Trust is the prerequisite, not a feature.** Every new capability should be evaluated: does this increase or decrease willingness to engage?

### What the platform does

4. **The engine defines structure; the vertical defines content.** The YAML compiler already embodies this principle.
5. **Deals need more than two parties.** Real transactions in thin markets require facilitators.
6. **The platform's job is to get parties to the table, not to run the table.** The initial deliverable is a Handoff Artifact, not a closed transaction.

### How information flows

7. **Privacy is a prerequisite.** Fewer participants means more identifiable data — privacy is not optional.
8. **Gallery is for discovery, matching is for depth.** Never conflate the two.
9. **Users own their information boundaries.** Per-document privacy must be editable at any time.
10. **Communication is scoped, not open.** Match or deal contexts only, not general messaging.
11. **Never destroy information through premature standardisation.** Dynamic schemas are the foundation.

### How we implement it

12. **Design for cognitive bandwidth constraints.** Curated subsets, not raw data dumps.
13. **Prompt-driven, not code-driven.** The prompt management system makes behaviour configurable without code changes.

---

*This roadmap will be updated as implementation progresses and as the thin market engine evolves.*
