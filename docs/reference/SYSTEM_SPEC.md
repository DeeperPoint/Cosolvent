# Cosolvent: Configurable Marketplace Platform — System Specification

> **Purpose of this document**: This is the definitive "what are we building" reference. Any developer or AI builder should be able to read this document alone and understand the full scope, constraints, and decisions behind the system. This document covers **what**, not **how** (architecture, tech stack, and implementation plans live elsewhere).

---

## Table of Contents

1. [Vision](#1-vision)
2. [Product Definition](#2-product-definition)
3. [Target Market Scope](#3-target-market-scope)
4. [Theoretical Foundation](#4-theoretical-foundation)
5. [Core Primitives](#5-core-primitives)
6. [Primitive 1 — Participant Types & Roles](#6-primitive-1--participant-types--roles)
7. [Primitive 2 — Profile & Onboarding](#7-primitive-2--profile--onboarding)
8. [Primitive 3 — Listings & Inventory](#8-primitive-3--listings--inventory)
9. [Primitive 4 — Discovery & Matching](#9-primitive-4--discovery--matching)
10. [Primitive 5 — Communication](#10-primitive-5--communication)
11. [Primitive 6 — Trust & Safety](#11-primitive-6--trust--safety)
12. [Supporting Infrastructure](#12-supporting-infrastructure)
13. [The Onboarding Wizard](#13-the-onboarding-wizard)
14. [Configuration vs. Fixed Behavior](#14-configuration-vs-fixed-behavior)
15. [MVP Scope & Boundaries](#15-mvp-scope--boundaries)
16. [Key Decisions Log](#16-key-decisions-log)
17. [Glossary](#17-glossary)

---

## 1. Vision

Build a **configurable marketplace template** that allows anyone to stand up a working marketplace backend rapidly. A marketplace creator goes through an onboarding wizard, defines their market's participants, rules, and workflows, and the system produces a fully configured, deployable marketplace.

This is not a hosted multi-tenant SaaS. It is an **open-source template** that teams clone from GitHub, configure through an onboarding experience, and deploy as their own single-tenant marketplace.

Think of it as: **a complete, working marketplace backend with a configuration layer that adapts it to different market types** — rather than a blank framework that requires building from scratch.

---

## 2. Product Definition

### What It Is

- A **configured template**: a complete, working marketplace system with opinionated defaults and configurable overrides.
- The onboarding wizard captures marketplace-specific decisions and writes them into a configuration that the template engine interprets at runtime.
- Single-tenant: one deployment = one marketplace.
- Deterministic: given the same configuration, the system behaves identically. No AI-generated code, no magic — just config-driven behavior.

### What It Is Not

- Not a code generator (it does not scaffold custom codebases per marketplace).
- Not a hosted platform (there is no central Cosolvent service running many marketplaces).
- Not a no-code builder (it produces a real backend that developers can extend).
- Not a generic CMS (it has real marketplace logic baked in — matching, communication, trust workflows).

### Deployment Model

1. Creator clones the repo from GitHub.
2. Creator runs the onboarding wizard (CLI or web-based).
3. Wizard captures decisions, produces a marketplace configuration file.
4. System reads that configuration at runtime and behaves accordingly.
5. Creator deploys their configured marketplace.
6. Creator can further customize by editing configuration or extending code.

---

## 3. Target Market Scope

### Primary Target (MVP)

**B2B marketplaces where participants have profiles, can discover each other, and communicate to transact.** This covers:

- Specialty agriculture (farmers ↔ mills ↔ distributors)
- Professional services (consultants ↔ companies)
- Industrial equipment (manufacturers ↔ buyers)
- Talent / recruiting (candidates ↔ employers)
- Cross-border trade (exporters ↔ importers)

### What These Markets Share

- Multiple participant types with different roles and permissions.
- Profiles that serve as (or accompany) listings.
- Discovery via search and/or AI-assisted matching.
- Structured communication flows between participants.
- Onboarding and verification workflows.
- Trust and visibility concerns (not everything is public to everyone).

### What Is Out of Scope for MVP

- Consumer-to-consumer marketplaces (eBay, Craigslist patterns).
- Real-time auction or bidding systems.
- Payment processing and escrow (trust mechanisms are informational, not transactional).
- Commodity exchange / order-book style trading.
- Multi-sided marketplaces with more than 3 participant types.

---

## 4. Theoretical Foundation

This system is grounded in the **Thin Markets** framework (see `WHITEPAPER.md`), which identifies ten forces of market physics that determine whether a market can function:

| # | Force | What It Means | How This System Addresses It |
|---|-------|--------------|------------------------------|
| 1 | Desire to Exchange | Do participants want to trade? | Out of scope — the marketplace creator validates this before using the tool |
| 2 | Opacity & Friction | How costly is it to find, verify, and complete a match? | **Discovery, matching, profile verification, AI search** |
| 3 | Physical Distance | Geographic separation of counterparties | **Configurable location/region attributes, search by geography** |
| 4 | Temporal Distance | Time separation of counterparties | **Asynchronous communication, notifications, always-available listings** |
| 5 | Information Density | How many details matter per item? | **Configurable profile/listing schemas with arbitrary attributes** |
| 6 | Fulfillment Options | Logistical constraints on delivery | Out of scope for MVP (no logistics/shipping management) |
| 7 | Friction-Free Market Size | How many participants could exist? | Out of scope — a property of the market, not the platform |
| 8 | Trust & Safety | Do participants feel secure? | **Verification workflows, visibility controls, approval flows** |
| 9 | Cognitive Bandwidth | Can participants process available info? | **AI-powered search, curated results, information synthesis** |
| 10 | Regulatory Friction | Legal framework constraints | Out of scope for MVP (marketplace creator handles compliance) |

The core engineering contribution of this platform addresses forces **2, 3, 4, 5, 8, and 9** — the forces that software can directly reduce.

---

## 5. Core Primitives

Every marketplace built with this system is composed of **six universal primitives** plus supporting infrastructure. Each primitive has configurable and fixed aspects.

```
┌─────────────────────────────────────────────────────────────┐
│                    MARKETPLACE INSTANCE                       │
│                                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐ │
│  │ 1. Participant │  │ 2. Profile &  │  │ 3. Listings &     │ │
│  │    Types &     │  │    Onboarding │  │    Inventory      │ │
│  │    Roles       │  │               │  │                   │ │
│  └───────────────┘  └───────────────┘  └───────────────────┘ │
│                                                               │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐ │
│  │ 4. Discovery  │  │ 5. Communi-   │  │ 6. Trust &        │ │
│  │    & Matching  │  │    cation     │  │    Safety         │ │
│  └───────────────┘  └───────────────┘  └───────────────────┘ │
│                                                               │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│  Supporting: Auth, Notifications, Files, AI/RAG Engine       │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Primitive 1 — Participant Types & Roles

### What This Primitive Does

Defines **who** participates in the marketplace and what each type is allowed to do.

### What the Old System Had

Four hardcoded types: `BUYER`, `PRODUCER`, `SERVICE_PROVIDER`, `ADMIN`. Permissions were implicit in route-level checks.

### What the New System Needs

The marketplace creator defines **1 to 3 participant types** (plus a system ADMIN type that always exists). Each type has:

- **A name** (e.g., "Farmer", "Mill", "Distributor", "Employer", "Candidate").
- **A role classification**: Is this type a **supply-side** participant (offers something), a **demand-side** participant (seeks something), or a **facilitator** (connects the other two)?
- **Permissions**: What actions can this type perform? (See table below.)

### Configurable Permissions Per Type

| Permission | Description | Example |
|-----------|-------------|---------|
| `can_list` | Can create listings/offerings | Producers can list products |
| `can_search` | Can search/discover other participants or listings | Buyers can search producers |
| `can_initiate_conversation` | Can start a conversation with another participant | Buyers can reach out to producers |
| `can_receive_conversation` | Can receive conversation requests | Producers receive buyer inquiries |
| `can_share_private_assets` | Can share private documents/files in conversations | Producers share spec sheets |
| `requires_onboarding` | Must complete onboarding before participating | Producers must be verified |
| `requires_approval` | Onboarding requires admin approval | Producers need admin review |
| `visible_in_search` | Profile/listings appear in search results | Producers are discoverable |

### Constraints

- Minimum 2 participant types (a marketplace needs at least two sides).
- Maximum 3 participant types for MVP (covering the two-sided + facilitator pattern from the old system).
- ADMIN type always exists and is not configurable — it has full access.
- Every marketplace must have at least one type that `can_search` and one that `is_visible_in_search`.

---

## 7. Primitive 2 — Profile & Onboarding

### What This Primitive Does

Defines **what information** each participant type provides and **how they get into the marketplace**.

### What the Old System Had

- Fixed profile schemas per role (producer fields, provider fields, buyer fields).
- A draft → review → submit → approve/reject pipeline.
- Document upload and AI-powered extraction during onboarding.
- AI-generated profile content (generate → approve/reject cycle).

### What the New System Needs

#### Profile Schema (Configurable Per Participant Type)

The marketplace creator defines the profile fields for each participant type. Each field has:

| Field Property | Description | Example |
|---------------|-------------|---------|
| `name` | Field identifier | `protein_content` |
| `label` | Display label | "Protein Content (%)" |
| `type` | Data type: `text`, `number`, `select`, `multi_select`, `date`, `file`, `rich_text`, `location` | `number` |
| `required` | Is this field mandatory? | `true` |
| `options` | For select/multi_select: the allowed values | `["Grade A", "Grade B", "Grade C"]` |
| `visibility` | Who can see this field: `public`, `protected`, `private` | `protected` |
| `searchable` | Is this field indexed for search/matching? | `true` |
| `section` | UI grouping for the profile form | "Quality Specifications" |

#### Onboarding Workflow (Configurable Per Participant Type)

The marketplace creator defines the onboarding flow for each participant type:

| Setting | Options | Default |
|---------|---------|---------|
| `requires_approval` | `true` / `false` | `true` for supply-side, `false` for demand-side |
| `approval_type` | `manual` (admin reviews) / `auto` (approved on submission) | `manual` |
| `document_upload_required` | `true` / `false` | `false` |
| `ai_extraction_enabled` | `true` / `false` — if true, uploaded documents are processed by AI to pre-fill profile fields | `false` |
| `ai_profile_generation` | `true` / `false` — if true, AI generates a polished profile summary from raw field data | `false` |
| `welcome_email_on_approval` | `true` / `false` | `true` |

#### Onboarding Lifecycle (Fixed)

The lifecycle pipeline itself is fixed (not configurable) because it is universal:

```
Account Created → Onboarding Form Presented → Draft Saved
  → Draft Submitted → [If approval required: Pending Review → Approved/Rejected]
  → [If approved or auto-approve: Profile Active]
  → [If rejected: Feedback Provided → User Can Resubmit]
```

---

## 8. Primitive 3 — Listings & Inventory

### What This Primitive Does

Defines **what is being offered or sought** in the marketplace, beyond participant profiles.

### What the Old System Had

No explicit listing model. Participant profiles functioned as implicit listings — a producer's profile was their "listing."

### What the New System Needs (MVP)

For MVP, we carry forward the **profile-as-listing** model from the old system. This means:

- A participant's profile IS their listing.
- Discovery is searching/browsing participant profiles.
- There is no separate "create a listing" flow — the profile schema captures what's being offered.

This works well for the MVP target markets:
- Professional services: the consultant's profile describes what they offer.
- Talent: the candidate's profile describes their skills; the employer's profile describes their needs.
- Specialty agriculture: the producer's profile describes what they grow and their quality specs.

#### Future Expansion (Post-MVP)

A dedicated listing model where participants can create multiple discrete listings (e.g., a farmer with multiple crop lots, an employer with multiple job openings). This would add:
- Listing schema (configurable fields, separate from profile fields).
- Listing lifecycle (draft → published → expired/sold).
- Listing-level search and matching (in addition to profile-level).

This is explicitly **out of scope for MVP** but should not be architecturally prevented.

---

## 9. Primitive 4 — Discovery & Matching

### What This Primitive Does

Allows participants to **find relevant counterparties** in the marketplace.

### What the Old System Had

- Keyword/filter-based search on producer and provider profiles.
- AI-powered vector search (semantic similarity via embeddings).
- RAG-powered Q&A ("find me a producer that...").
- Search result visibility based on authentication and role.

### What the New System Needs

#### Search (Configurable)

| Setting | Description | Default |
|---------|-------------|---------|
| `searchable_types` | Which participant types appear in search results | All types with `visible_in_search = true` |
| `search_fields` | Which profile fields are indexed for search | All fields marked `searchable = true` |
| `filter_fields` | Which fields appear as filterable facets in the search UI | Subset of searchable fields with `type = select` or `number` |
| `result_visibility` | What profile data is shown in search results by auth state: `anonymous`, `authenticated`, `same_type`, `different_type` | `anonymous` sees `public` fields, `authenticated` sees `public + protected` |

#### AI-Assisted Discovery (Configurable)

| Setting | Description | Default |
|---------|-------------|---------|
| `vector_search_enabled` | Enable semantic similarity search via embeddings | `true` |
| `rag_query_enabled` | Enable natural-language Q&A over the marketplace knowledge base | `true` |
| `follow_up_suggestions` | AI suggests follow-up queries after search | `true` |
| `retrieval_filters` | Metadata dimensions available for filtering RAG results (e.g., country, participant type) | Derived from `filter_fields` |

#### Matching Approach (MVP)

For MVP, matching is **attribute-based + semantic**:

1. **Attribute matching**: Filter by structured fields (location, grade, category, price range).
2. **Semantic matching**: Vector similarity over profile text (descriptions, capabilities, needs).
3. **Combined**: Attribute filters narrow the pool, semantic ranking orders the results.

This covers the MVP target markets:
- Specialty agriculture: filter by crop type and region, rank by quality spec similarity.
- Professional services: filter by industry and location, rank by capability match.
- Talent: filter by role and experience level, rank by skill/culture description similarity.

No marketplace-type-specific matching archetypes for MVP. One matching pipeline, configurable through which fields are searchable and which are facets.

---

## 10. Primitive 5 — Communication

### What This Primitive Does

Enables participants to **talk to each other** within the marketplace.

### What the Old System Had

Two hardcoded conversation tracks:
1. **Buyer → Producer**: Buyer initiates → Producer accepts/rejects → messaging begins.
2. **Buyer/Producer → Service Provider**: Either initiates → Provider accepts/rejects → messaging begins.

Features per track: text/image/video/audio/file messages, real-time WebSocket delivery, message editing/deletion, private asset sharing into conversations, notification side effects.

### What the New System Needs

#### Interaction Rules (Configurable)

The marketplace creator defines **which participant type can initiate conversations with which other type**, and what the initiation flow looks like.

This is expressed as a set of **conversation rules**:

```
conversation_rules:
  - initiator: "Buyer"          # Which type can start this conversation
    receiver: "Producer"        # Which type receives the request
    requires_approval: true     # Does the receiver need to accept before messaging begins?

  - initiator: "Buyer"
    receiver: "Service Provider"
    requires_approval: true

  - initiator: "Producer"
    receiver: "Service Provider"
    requires_approval: true
```

Each rule defines:

| Setting | Description | Default |
|---------|-------------|---------|
| `initiator` | Participant type that can start the conversation | Required |
| `receiver` | Participant type that receives the request | Required |
| `requires_approval` | Must the receiver explicitly accept before messaging begins? | `true` |

#### Conversation Features (Fixed for MVP)

These features are always available in every conversation — not configurable:

- **Message types**: text, image, video, audio, file.
- **Real-time delivery**: WebSocket transport for live messaging.
- **Message operations**: create, edit (own messages only), delete (own messages only).
- **Private asset sharing**: Participants with `can_share_private_assets` permission can share files into active conversations.
- **Conversation states**: `pending` (awaiting approval) → `active` (messaging enabled) → `closed` (archived).

#### Notification Side Effects (Fixed)

Every conversation event generates a notification:
- Conversation request received.
- Conversation approved/declined.
- New message received.

---

## 11. Primitive 6 — Trust & Safety

### What This Primitive Does

Ensures participants **feel secure enough to engage** with the marketplace and each other.

### What the Old System Had

- Role-based visibility (public vs. protected profile data).
- Admin-gated onboarding approval.
- Conversation participant-only access to messages.
- Ownership constraints on message editing/deletion.

### What the New System Needs

#### Visibility Controls (Configurable)

Profile field visibility is configured per field (see Primitive 2). The three visibility tiers are fixed:

| Tier | Who Can See | Use Case |
|------|------------|----------|
| `public` | Anyone, including unauthenticated visitors | Company name, general description, location |
| `protected` | Authenticated marketplace participants | Detailed quality specs, pricing ranges, contact info |
| `private` | Only the profile owner and admins | Internal documents, financial details, strategic notes |

#### Verification Workflows (Configurable)

| Setting | Description | Default |
|---------|-------------|---------|
| `admin_approval_required` | New participants of this type require admin approval | Configurable per type |
| `document_verification` | Require document upload during onboarding (certifications, business registration, etc.) | `false` |
| `profile_completeness_threshold` | Minimum percentage of required fields that must be filled before profile goes active | `100%` |

#### Platform Safety (Fixed)

These are always active and not configurable:
- Conversation access restricted to participants only.
- Message edit/delete restricted to message owner.
- Admin override access to all conversations and profiles.
- Rate limiting on conversation initiation (prevent spam).

---

## 12. Supporting Infrastructure

These are **not marketplace-logic primitives** but are required services. They are largely fixed (not configurable by the marketplace creator) because they work the same way regardless of market type.

### Authentication & Sessions

- Email/password account creation and sign-in.
- Session issuance and verification.
- Role- and type-aware user records.
- Onboarding state tracking.
- Admin bootstrap path.

**Carried forward from old system as-is.** No marketplace-specific configuration needed.

### Notifications

- Persist notifications per user.
- List a user's notifications.
- Mark as read.
- Notification types are derived from the configured conversation rules and onboarding workflows.

**Carried forward from old system, with notification types now dynamic** (driven by which conversation rules and onboarding workflows are configured).

### File & Asset Management

- Upload files and media.
- Associate files with profiles or conversations.
- Privacy levels on files (public, protected, private).
- Private asset sharing into conversations.

**Carried forward from old system as-is.**

### AI / RAG Engine

- Query answering with thread continuity.
- Follow-up question generation.
- Knowledge-base document ingestion and indexing.
- Vector search over profile data.
- AI profile content generation (when enabled per type).
- AI document extraction during onboarding (when enabled per type).
- LLM settings and prompt configuration (admin-managed).

**Carried forward from old system.** The AI engine reads the marketplace configuration to understand what participant types exist, what fields matter, and how to frame its responses. The prompts and retrieval filters adapt to the configured marketplace schema.

### API Gateway

- Path-based routing to backend services.
- WebSocket upgrade handling.
- Rate limiting and request-size policies.
- CORS configuration.

**Carried forward from old system as-is.**

---

## 13. The Onboarding Wizard

The onboarding wizard is the **creator-facing experience** that captures marketplace configuration. It runs once (or can be re-run to reconfigure) and produces the marketplace configuration file that the system reads at runtime.

### Wizard Steps

#### Step 1: Marketplace Identity

Capture basic information about the marketplace:
- Marketplace name.
- Description / purpose.
- Target industry or market vertical (informational — used for AI prompt context).

#### Step 2: Participant Types

Define the participant types (2–3 types + ADMIN):
- For each type: name, role classification (supply/demand/facilitator).
- For each type: which permissions apply (from the permissions table in Primitive 1).

#### Step 3: Profile Schemas

For each participant type, define profile fields:
- Field name, label, data type, required/optional, visibility tier, searchable flag.
- Group fields into sections for UI organization.
- Optionally: enable AI document extraction and/or AI profile generation for this type.

#### Step 4: Onboarding Workflows

For each participant type:
- Requires approval? Manual or auto?
- Document upload required?
- Welcome email on approval?

#### Step 5: Communication Rules

Define conversation rules:
- Which type can initiate with which type?
- Does each track require approval?

#### Step 6: Discovery Configuration

Configure search and matching:
- Which types are searchable?
- Which fields are filterable facets?
- Enable/disable AI features (vector search, RAG Q&A, follow-up suggestions).

#### Step 7: Review & Generate

- Display a summary of all configuration choices.
- Creator confirms.
- Wizard writes the marketplace configuration file.
- System is ready to deploy.

### Wizard Output

A single **marketplace configuration file** (likely JSON or YAML) that contains all decisions from the wizard. This file is the single source of truth for how the marketplace behaves.

---

## 14. Configuration vs. Fixed Behavior

This table summarizes what is configurable by the marketplace creator and what is fixed in the template.

### Configurable (Set During Onboarding)

| Aspect | What's Configurable |
|--------|-------------------|
| Participant types | Names, count (2–3), role classification |
| Permissions per type | Which actions each type can perform |
| Profile schema per type | Fields, data types, visibility, searchability |
| Onboarding flow per type | Approval required, document upload, AI extraction, AI profile gen |
| Communication rules | Who can initiate with whom, approval required per track |
| Search configuration | Searchable types, filter facets, AI feature toggles |
| Marketplace identity | Name, description, industry context |

### Fixed (Baked Into the Template)

| Aspect | What's Fixed |
|--------|-------------|
| Auth system | Email/password, session-based, role-aware |
| Onboarding lifecycle | Draft → submit → review → approve/reject pipeline |
| Conversation lifecycle | Pending → active → closed states |
| Message features | Text, image, video, audio, file; edit/delete own; WebSocket delivery |
| Visibility tiers | Public, protected, private (three tiers, always) |
| Notification system | Create, list, mark-read; types derived from config |
| Admin capabilities | Full access, always present |
| File management | Upload, associate, privacy levels |
| AI engine | RAG, vector search, prompt management, document ingestion |
| API gateway pattern | Path-based routing, WebSocket support, rate limiting |
| Security model | Session auth, participant-only conversation access, ownership constraints |

---

## 15. MVP Scope & Boundaries

### In Scope for MVP

- Onboarding wizard that produces a marketplace configuration file.
- Configurable participant types (2–3 types + admin).
- Configurable profile schemas per type.
- Configurable onboarding workflows (with approval pipeline).
- Configurable communication rules (request/approve pattern).
- Profile-as-listing discovery model.
- Attribute-based + semantic search over profiles.
- AI-powered features carried from old system: vector search, RAG Q&A, AI profile generation, AI document extraction.
- Real-time messaging with WebSocket delivery.
- Notification system.
- File and private asset management.
- Admin dashboard with metrics.

### Explicitly Out of Scope for MVP

| Feature | Why Deferred |
|---------|-------------|
| Separate listing model (multiple listings per participant) | Profile-as-listing sufficient for MVP target markets |
| Payment processing / escrow | Adds massive complexity; participants handle payments externally |
| Advanced interaction patterns (match-first, broker-mediated, tiered disclosure) | Request/approve pattern covers MVP; others are post-MVP |
| Multi-tenant hosting | Single-tenant clone-and-deploy model for MVP |
| Consumer marketplace patterns (auctions, bidding, cart/checkout) | Out of target market |
| Logistics / fulfillment management | Out of scope entirely |
| Mobile-first / voice-first interfaces | Post-MVP |
| Advanced AI: trusted intermediary, asynchronous AI brokerage, psychological framing | Post-MVP; requires MVP foundation first |
| More than 3 participant types | Covers vast majority of marketplace patterns; extend post-MVP |

### Success Criteria for MVP

A marketplace creator should be able to:
1. Clone the repo.
2. Run the onboarding wizard.
3. Define their participant types, profiles, rules.
4. Deploy a working marketplace where participants can sign up, onboard, discover each other, and communicate.
5. All of this works correctly out of the box with zero custom code required.

---

## 16. Key Decisions Log

These decisions were made during the specification phase. They are recorded here so future work can understand the reasoning.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Single-tenant deployment model** — each marketplace is its own deployment, cloned from GitHub | Simplicity. Multi-tenant adds shared infrastructure, isolation concerns, and billing complexity that are not needed at this stage. |
| D2 | **Configured template, not code generation** — one codebase reads a config file at runtime | Deterministic behavior. Easier to maintain, update, and reason about. Marketplace creators benefit from upstream template improvements. |
| D3 | **Profile-as-listing for MVP** — no separate listing entity | Reduces scope while covering the primary target markets. The profile schema is flexible enough to capture what's being offered. Separate listings are a clean post-MVP addition. |
| D4 | **Request/approve communication pattern for MVP** — other interaction patterns deferred | This is the most universal pattern, proven in the old system, and sufficient for B2B contexts where unsolicited contact should be gated. |
| D5 | **Carry forward old system's AI capabilities** — vector search, RAG, AI profile generation, document extraction | These are proven, working features. Solidifying them in the new configurable architecture is the priority before adding whitepaper-level AI capabilities (trusted intermediary, etc.). |
| D6 | **Maximum 3 participant types + admin** — not unlimited | Covers two-sided marketplaces and the three-sided pattern (buyer + seller + facilitator). More types create exponential complexity in communication rules and permissions. |
| D7 | **Three fixed visibility tiers** — public, protected, private | Simple mental model. Covers the real-world needs: marketing-facing, participant-facing, and owner-only. More granular access control is post-MVP. |
| D8 | **Target: B2B profile-discovery-communication marketplaces** | This is the sweet spot where the old system's strengths (onboarding, profiles, messaging, AI search) apply broadly. Consumer marketplaces and exchange-style trading have fundamentally different dynamics. |

---

## 17. Glossary

| Term | Definition |
|------|-----------|
| **Marketplace Creator** | The person/team who clones the template, runs the onboarding wizard, and deploys their marketplace. They are a developer or technical team. |
| **Participant** | An end-user of a deployed marketplace. Has a type (e.g., Buyer, Producer) and interacts with other participants. |
| **Participant Type** | A category of participant defined by the marketplace creator (e.g., "Farmer", "Mill", "Employer"). Each type has its own profile schema, permissions, and onboarding rules. |
| **Configuration File** | The output of the onboarding wizard. A structured file (JSON/YAML) that defines all marketplace-specific behavior. The single source of truth. |
| **Onboarding Wizard** | The creator-facing experience that captures marketplace configuration decisions through a guided flow. |
| **Profile-as-Listing** | The model where a participant's profile serves as their marketplace listing. No separate "create a listing" flow exists. |
| **Conversation Rule** | A configured rule defining which participant type can initiate conversations with which other type, and whether approval is required. |
| **Supply-side** | Participant types that offer something (goods, services, expertise). |
| **Demand-side** | Participant types that seek something (buyers, hirers, procurement). |
| **Facilitator** | Participant types that connect supply and demand (brokers, service providers, consultants). |
| **Visibility Tier** | One of three access levels for profile data: `public` (anyone), `protected` (authenticated participants), `private` (owner + admin only). |
| **Thin Market** | A market where buyers and sellers struggle to find each other, transactions are infrequent, and beneficial exchanges fail to occur despite willing participants. The core problem this platform addresses. |
| **Market Physics** | The fundamental, unchangeable forces that determine whether a market can function (from the whitepaper). |
| **Market Engineering** | Interventions and tools that can overcome friction and enable thick market behavior (from the whitepaper). |

---

## Appendix: Mapping Old System → New System

This table maps every capability from the old system (`docs/archive/OLD.md`) to its new-system equivalent, confirming nothing is lost.

| Old System Capability | New System Location | Change |
|-----------------------|-------------------|--------|
| Auth: email/password, sessions, roles | Supporting Infrastructure: Auth | **Same**, but user types are now dynamic (read from config instead of hardcoded enum) |
| Profile: producer/provider/buyer schemas | Primitive 2: Profile Schema | **Configurable** — schemas defined per participant type in config |
| Profile: draft → review → approve pipeline | Primitive 2: Onboarding Lifecycle | **Same pipeline**, but approval settings configurable per type |
| Profile: document upload + AI extraction | Primitive 2: Onboarding Workflow | **Same**, toggled on/off per participant type in config |
| Profile: AI-generated content | Primitive 2: AI Profile Generation | **Same**, toggled on/off per participant type in config |
| Profile: templates | Primitive 2: Profile Schema | **Replaced** by configurable profile schemas — templates are no longer needed as a separate concept |
| Profile: search (keyword + vector) | Primitive 4: Discovery & Matching | **Same capabilities**, but searchable fields and facets configured per marketplace |
| Profile: private assets | Supporting Infrastructure: Files | **Same** |
| Profile: public/protected visibility | Primitive 6: Visibility Controls | **Same three tiers**, now configured per field instead of per entity |
| Communication: buyer→producer track | Primitive 5: Conversation Rules | **Configurable** — expressed as a conversation rule instead of hardcoded track |
| Communication: initiator→provider track | Primitive 5: Conversation Rules | **Configurable** — expressed as a conversation rule instead of hardcoded track |
| Communication: messages (text/media/file) | Primitive 5: Conversation Features | **Same** |
| Communication: WebSocket real-time | Primitive 5: Conversation Features | **Same** |
| Communication: private asset sharing | Primitive 5: Conversation Features | **Same**, gated by `can_share_private_assets` permission |
| Notifications: create/list/read | Supporting Infrastructure: Notifications | **Same**, notification types now dynamic |
| Personalization: RAG Q&A | Primitive 4: AI-Assisted Discovery | **Same** |
| Personalization: vector search | Primitive 4: AI-Assisted Discovery | **Same** |
| Personalization: settings-manager assistant | Supporting Infrastructure: AI Engine | **Same** |
| Personalization: FAQ management | Supporting Infrastructure: AI Engine | **Same** |
| Personalization: LLM/prompt config | Supporting Infrastructure: AI Engine | **Same** |
| Personalization: document ingestion | Supporting Infrastructure: AI Engine | **Same** |
| API Gateway: routing, WebSocket, rate limiting | Supporting Infrastructure: API Gateway | **Same** |
| Admin: dashboard metrics | Supporting Infrastructure: Admin | **Same** |

**Nothing from the old system is dropped.** Everything is either carried forward as-is or made configurable through the new configuration layer.
