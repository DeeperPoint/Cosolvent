# CONVERGENCE — Market Forge

> **Copyright © 2026 Mustafa Uzumeri. All rights reserved.**
>
> **Date:** February 21, 2026
> **Status:** Design specification
> **Working name:** "Market Forge" is a placeholder. The name may change to avoid potential conflicts with existing uses (Market Forge Industries / Middleby Corporation in commercial kitchen equipment; MarketForge.tech in marketplace apps).
> **Prerequisites:** `ROADMAP.md` (this repo), `ClientSynthAI/ROADMAP.md`, `AIKnowledgeSlotCuration/ROADMAP.md`, `CosolventAI/ROADMAP.md`
> **Related:** `CosolventAI/docs/session-notes/2026-02-18-strategic-packaging.md`, Whitepaper Chapters 33–35

---

## 1. Executive Summary

The **Market Forge** is the convergence of three existing tools into a single workflow that produces a functioning digital twin of a proposed thin market. Given a market description and domain reference materials, the Forge:

1. **Curates domain knowledge** — ingests trade regulations, quality standards, contract templates, and procedural guides (AIKnowledgeSlotCuration)
2. **Generates marketplace configuration** — extracts participant types, profile schemas, matching prompts, and deal parameters from the domain knowledge
3. **Synthesizes a realistic population** — generates demographically plausible, economically coherent, culturally appropriate synthetic participants (ClientSynth)
4. **Stands up a configured marketplace** — compiles and populates a Cosolvent instance with the reference library, configuration, and synthetic population
5. **Runs simulation scenarios** — executes matching, deal assembly, facilitator search, and Handoff Artifact generation against the synthetic population
6. **Validates the business design** — the sponsor uses the digital twin as a sandbox to pretest value-added services (sample fulfillment, market analytics, trade finance integration) with real service providers against the synthetic population
7. **Transitions to a real market** — synthetic participants are retired entirely and real participants are recruited by the sponsor into a production instance

The output progresses from a **clickable, demonstrable prototype** (Phases 1–6) through a **business design sandbox** (Phase 7) to a **live marketplace** (Phase 8). This is the whitepaper's Chapter 35 vision made operational — and extended through to market launch.

---

## 2. The Three Tools and Their Roles

| Tool                        | What it produces                                                                                                                                | Digital Twin role                                                                        | Current state                                                                                                                                                                                        |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **AIKnowledgeSlotCuration** | Markdown reference documents, domain metadata schemas (YAML), provenance records, extraction prompts                                            | **The rules of the game** — regulations, standards, and contracts that govern the market | Working: document conversion, provenance tracking, metadata extraction. Missing: ingestion-ready output format for Cosolvent's `reference_library`                                                   |
| **ClientSynth**             | Synthetic participant populations — AI-generated profiles with configurable schemas, demographic distributions, and behavioral parameters       | **The players** — who would participate, with what capabilities and needs                | Working: multi-tenant schema designer, AI generation, export system. Missing: Cosolvent export format, MarketDefinition import, domain-aware vocabulary                                              |
| **Cosolvent (beta)**        | Marketplace infrastructure — YAML-driven configuration, semantic matching, communication, facilitator types, admin oversight, prompt management | **The arena** — the operational mechanics that connect participants and facilitate deals | Working: YAML configuration, dynamic profiles, pgvector search, admin tools, prompt management, document processing. Missing: Deal entity, Handoff Artifact, Knowledge Slot, ClientSynth integration |

### What makes this convergence non-obvious

The three tools were developed independently with different proximate goals. The insight is that their outputs form a **closed triangle** — each tool's output is another tool's input:

```
     AIKnowledgeSlotCuration
            ╱           ╲
    domain schema    reference library
     + vocabulary      + metadata
          ╱                 ╲
   ClientSynth ────────── Cosolvent
     synthetic          marketplace
     population ──────► instance
```

The missing connector — **domain schema informing ClientSynth's generation vocabulary** — is the piece that closes the loop and makes the system self-consistent rather than three separate tools producing loosely related outputs.

---

## 3. Integration Points — Current and Required

### 3.1 Existing connections (designed but not built)

| From → To                           | Interface                                              | Status                             | Roadmap reference                         |
| ----------------------------------- | ------------------------------------------------------ | ---------------------------------- | ----------------------------------------- |
| AIKnowledgeSlotCuration → Cosolvent | Reference documents → `reference_library` table        | Designed in both roadmaps          | Cosolvent ROADMAP §16.2; AIKSC ROADMAP §5 |
| ClientSynth → Cosolvent             | Synthetic participants → Cosolvent participant records | Partially designed (file-based C0) | ClientSynth ROADMAP Track C               |
| ClientSynth → Cosolvent             | MarketDefinition YAML → ClientSynth schema templates   | Conceptual (C1.1)                  | ClientSynth ROADMAP Track C               |

### 3.2 Missing connections (not yet on any roadmap)

| From → To                                      | Interface                                               | What it enables                                                                                                     | Priority                                                  |
| ---------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **AIKnowledgeSlotCuration → ClientSynth**      | Domain schema YAML → generation vocabulary constraints  | Synthetic participants use real-world terminology (GAFTA grades, not random strings). Schema-conformant profiles.   | **Critical** — without this, synthetic data is generic    |
| **AIKnowledgeSlotCuration → Cosolvent config** | Domain schema → `marketplace.yaml` generation           | Automatic configuration of participant types, profile fields, matching prompts, Deal Brief templates                | **Critical** — without this, marketplace config is manual |
| **Cosolvent config → ClientSynth**             | `marketplace.yaml` → population specification           | ClientSynth knows how many of each participant type to generate, what fields to populate, what distributions to use | **High** — enables automated population scaling           |
| **Cosolvent simulation → Analytics**           | Deal outcomes, match quality, market dynamics → reports | Quantitative evidence for sponsors/investors                                                                        | **Medium** — needed for Use Cases 2 and 3 (Ch. 35)        |

---

## 4. The Matured Workflow

When all integration points are built, the end-to-end workflow for creating a market digital twin looks like this:

### Phase 1: Market Description (Human + AI)

**Input:** A natural-language market description, plus reference materials.

> *Example: "Cross-border specialty grain trade between Western Canada and Southeast Asia. Canadian exporters of malting barley, durum wheat, and canola. Asian importers including mills, feed manufacturers, and food processors in the Philippines, Indonesia, Vietnam, and Thailand. Facilitators include customs brokers, grain inspectors, shipping agents, and trade finance providers."*

**Activities:**
1. Sponsor describes the market in natural language
2. Sponsor uploads or points to reference materials (regulatory documents, trade agreements, quality standards, contract templates, industry guides)
3. AI assists in refining the market description through structured dialogue — eliciting participant types, geographic scope, regulatory jurisdictions, product categories, and deal structure

**Output:** Structured market brief + uploaded reference documents

---

### Phase 2: Knowledge Curation (AI + Human review)

**Tool:** AIKnowledgeSlotCuration

**Activities:**
1. Reference documents are converted to Markdown (PDF, HTML, DOCX, CSV, XLSX → MD)
2. Provenance metadata is extracted or imputed (organization, date, document type, jurisdiction)
3. Domain schema is extracted — a YAML vocabulary defining:
   - Participant type taxonomy (roles, categories)
   - Profile field definitions per participant type
   - Product/service attribute vocabulary
   - Geographic scope (origin regions, destination countries, trade corridors)
   - Regulatory context (jurisdictions, standards bodies, compliance requirements)
   - Quality grading systems and their valid values
   - Deal term categories (what issues are negotiable in this market)
4. Documents are chunked, embedded, and tagged with the domain schema's metadata vocabulary
5. Human reviews and refines the domain schema

**Output:**
- `domain_schema.yaml` — the vertical's vocabulary and structure
- `reference_library/` — chunked, embedded, metadata-tagged reference documents
- `extraction_prompts/` — LLM prompts tuned for this domain's metadata extraction

---

### Phase 3: Marketplace Configuration (AI + Human review)

**Tool:** Cosolvent configuration generator (new component)

**Activities:**
1. `domain_schema.yaml` is read and transformed into a `marketplace.yaml`:
   - Participant types → Cosolvent participant type definitions
   - Profile fields → dynamic profile schema (JSONB structure per type)
   - Deal term categories → issue types for the Deal State Machine
   - Regulatory context → compliance flag configuration
   - Geographic scope → geographic filters and shipping corridor definitions
2. Matching prompts are generated from the domain schema (what dimensions matter for semantic matching in this vertical)
3. Deal Brief template is generated (vertical-specific name, sections, field mappings)
4. Facilitator role slot definitions are generated (what facilitator types exist, which are required vs. optional per deal type)
5. Human reviews and adjusts the generated marketplace.yaml

**Output:**
- `marketplace.yaml` — complete Cosolvent deployment configuration
- `prompts/` — matching, extraction, brokerage, and rationale prompts
- `deal_brief_template.yaml` — Handoff Artifact structure

---

### Phase 4: Population Synthesis (AI + Human review)

**Tool:** ClientSynth

**Activities:**
1. ClientSynth reads the `marketplace.yaml` and `domain_schema.yaml`
2. Population specification is derived:
   - Participant types and counts (configurable, with sensible defaults based on market size estimates in the brief)
   - Profile field distributions per type (e.g., 40% of Canadian exporters are in Saskatchewan, 25% in Alberta, etc.)
   - Vocabulary constraints from domain schema (quality grades use GAFTA terminology, certifications reference real standards bodies)
   - Economic coherence rules (farm sizes correlate with production volumes, buyer demand correlates with mill capacity)
   - Geographic distribution respecting the market's trade corridors
3. Synthetic participants are generated with full profiles
4. Human reviews sample profiles for plausibility

**Output:**
- `population.json` — synthetic participant records conforming to the marketplace schema
- `population_metadata.json` — generation parameters, distributions used, vocabulary sources

---

### Phase 5: Assembly and Deployment (Automated)

**Tool:** Cosolvent (beta) deployment pipeline

**Activities:**
1. Reference library is loaded into the `reference_library` table with metadata tags
2. Marketplace configuration is compiled (marketplace.yaml → runtime config)
3. Synthetic participants are loaded into the `participants` table with properly structured JSONB profiles
4. Participant embeddings are generated and indexed in pgvector
5. System prompts are loaded from the generated prompt set
6. Health checks confirm the instance is operational

**Output:**
- Running Cosolvent instance with populated marketplace

---

### Phase 6: Simulation and Demonstration (Human + AI)

**Activities:**
1. **Gallery browsing** — browse synthetic participant profiles as different participant types
2. **Match generation** — run semantic matching to find buyer-seller pairs
3. **Deal assembly** — initiate deals between matched pairs, observe issue-level negotiation flow
4. **Facilitator search** — trigger deal-triggered facilitator discovery for required role slots
5. **Handoff Artifact generation** — complete a deal and generate the Deal Brief / Plan of Care / Production Brief
6. **Knowledge Slot Q&A** — query the reference library from a participant's perspective ("What regulations apply to exporting malting barley to the Philippines?")
7. **Market dynamics reporting** — aggregate match quality, deal completion rates, facilitator utilization, and other metrics
8. **Demo Mode preparation** — pre-compute results and configure for public showcase (see below)

**Output:**
- Demonstrable prototype with realistic market activity
- Market dynamics report with quantitative evidence
- Recorded walkthrough (video or interactive)
- **Public demo instance** (read-only, zero cost per visit)

#### Phase 6a: Demo Mode — Public Showcase Capability

Once Phase 6 has produced a working digital twin with realistic market activity, the instance can be switched to **Demo Mode** — a read-only, publicly accessible showcase that lets visitors experience the marketplace from the perspective of a synthetic participant. This is the "try it yourself" version of the demo.

**Demo Mode has two components: an admin switch and a visitor onboarding flow.**

##### Admin Mode Switch

An administrative toggle that puts the entire Cosolvent instance into demo mode:

| Setting                        | Live mode (default) | Demo mode                                                                                                                                    |
| ------------------------------ | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Database writes**            | Allowed             | **Blocked** — all data is read-only                                                                                                          |
| **User-initiated LLM prompts** | Allowed             | **Blocked** — no free-form LLM calls; only curated prompt buttons are available (returning pre-computed results)                             |
| **Authentication**             | Full login          | **Persona assignment only** — visitors are assigned a synthetic identity, not a real account                                                 |
| **Data persistence**           | Normal              | **None** — visitor sessions are ephemeral; nothing is saved                                                                                  |
| **Admin access**               | Full admin panel    | Admin panel remains accessible to the operator (password-protected) for toggling mode, monitoring traffic, and updating pre-computed content |

**Why block live LLM calls:** A publicly accessible demo that runs live LLM prompts is an open cost liability and an abuse vector. Every visitor question costs money; adversarial visitors can prompt-inject. Hard-coded prompts returning pre-computed results look identical to the visitor but cost nothing per visit and cannot be exploited.

##### Visitor Onboarding — Stratified Persona Assignment

When a visitor arrives at a demo-mode instance, they go through a lightweight onboarding that assigns them a synthetic persona:

**Step 1: Role selection (stratified)**
> *"Welcome to the Canada–Southeast Asia Specialty Grain Marketplace.*
> *Would you like to explore as a:*
> - 🌾 *Grain Exporter (Canada)*
> - 🏭 *Mill / Processor (Southeast Asia)*
> - 🚢 *Shipping & Logistics Provider*
> - 🔬 *Grain Inspector / Quality Certifier*
> - 🏦 *Trade Finance Provider"*

**Step 2: Random persona assignment**

The system randomly selects one synthetic participant of the chosen type and "logs the visitor in" as that persona. The visitor sees:
- The persona's profile (name, company, location, capabilities, certifications)
- The persona's match gallery (pre-computed top matches)
- The persona's view of the marketplace (filtered by their type and geography)

**Step 3: Guided exploration**

The visitor navigates the marketplace as their assigned persona. At each screen, curated **"Ask about this"** buttons are available instead of free-form input:

| Screen                 | Curated prompts (examples)                                                                                                          | What the visitor sees                       |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| **My Profile**         | "How does my profile compare to other exporters?"                                                                                   | Pre-computed peer comparison                |
| **Match Gallery**      | "Why was this buyer matched to me?"                                                                                                 | Pre-computed matching rationale             |
| **Deal View**          | "What would a typical deal with this buyer look like?"                                                                              | Pre-computed sample Deal Brief              |
| **Knowledge Slot**     | "What regulations apply to exporting malting barley to the Philippines?" / "What GAFTA contract terms are standard for this trade?" | Pre-computed Q&A from the reference library |
| **Facilitator Search** | "Who can inspect my grain before export?" / "Which shipping agents serve the Saskatoon–Manila corridor?"                            | Pre-computed facilitator recommendations    |
| **Market Overview**    | "How thick is the Canada–Philippines barley corridor?" / "Where are the facilitator gaps?"                                          | Pre-computed market analytics               |

**Step 4: Session end**

When the visitor leaves (closes browser, times out, or clicks "Exit"), the session evaporates. No data is collected, no cookies persist, no account is created. The visitor can return and be assigned a different persona.

##### Pre-Computation Layer

For Demo Mode to work, a **pre-computation step** runs once (or on-demand when the admin updates the demo) to bake all results:

| Pre-computed artifact          | Source                                                                                          | Storage    |
| ------------------------------ | ----------------------------------------------------------------------------------------------- | ---------- |
| **Match results per persona**  | pgvector semantic matching, run for every synthetic participant                                 | JSON cache |
| **Match rationale per pair**   | LLM-generated explanation for each top-N match                                                  | JSON cache |
| **Sample Deal Briefs**         | 3–5 completed deals per participant type, with full Handoff Artifact content                    | JSON cache |
| **Knowledge Slot Q&A**         | 5–10 curated questions per participant type, answered against the reference library             | JSON cache |
| **Facilitator search results** | Pre-computed facilitator recommendations for each deal type / corridor                          | JSON cache |
| **Market analytics**           | Aggregate statistics: match density, corridor traffic, facilitator utilization, pricing signals | JSON cache |
| **Peer comparisons**           | Profile comparisons within each participant type                                                | JSON cache |

**Pre-computation cost:** One-time LLM cost for generating all rationales, Q&A answers, and deal narratives. For a population of 100 synthetic participants with 10 curated prompts each, this is approximately 1,000 LLM calls — a one-time cost of $5–$50 depending on model and prompt complexity. After that, every visitor interaction is a cache lookup.

##### Design Rationale

This approach solves three problems simultaneously:

1. **Cost control** — Zero marginal cost per visitor. The demo can be linked on a website, shared on social media, or embedded in a pitch deck without worrying about LLM bills.

2. **Security** — No prompt injection risk, no data exfiltration risk, no write access to any database. The worst a malicious visitor can do is click buttons and read pre-computed content.

3. **Multi-perspective demonstration** — Different visitors see different perspectives of the same market. A visitor who selects "Grain Exporter" and one who selects "Mill/Processor" experience the same marketplace from opposite sides. This implicitly demonstrates the platform's multi-sided matching capability without anyone having to explain it.

##### Optional Enhancement: Limited Live Queries

As a future enhancement, a small number of **live LLM queries per session** (e.g., 3 "ask anything" questions) could be enabled behind a gate (captcha, email capture, or access code). This is dramatically more impressive — the visitor asks their own question about regulations or market conditions and gets a real, contextual answer. However, it reintroduces cost and abuse risk and should only be enabled for controlled demo contexts (e.g., scheduled investor walkthroughs, trade show booths with staff present).

---

### Phase 7: Value-Added Service Pretesting (Sponsor + Real Service Providers + Synthetic Participants)

This phase uses the digital twin as a **business design sandbox**. The marketplace is populated with synthetic participants, but the services being tested may involve real-world actors — a real bank, a real logistics provider, a real compliance advisor. The synthetic population provides the demand context; the real service providers test whether their offerings integrate with the platform.

**Why this phase exists:** A marketplace alone is not a business. The sponsor's revenue model depends on value-added services that layer onto or beside the core matching-and-deal infrastructure. The digital twin lets the sponsor pretest these services before committing to real participant recruitment.

**Activities:**

1. **Sample fulfillment testing** — Using deal parameters from completed synthetic deals, test whether a physical sample (not a commercial order) can move through the logistics chain. "Can we ship 2 kg of malting barley from Saskatoon to a mill in Davao City, with all the correct customs documentation, certificates of analysis, and phytosanitary certificates?" This validates that the Handoff Artifact / Deal Brief contains enough information to drive real-world logistics — without commercial risk.

2. **Market analytics product testing** — The digital twin generates match data, deal patterns, facilitator utilization, corridor traffic, and pricing signals. The sponsor tests whether these analytics have standalone value:
   - "Here is the match density for Canada → Philippines malting barley: 12 plausible buyer-seller pairs out of a population of 80."
   - "Average estimated deal size: $CAD 180K. Average Deal Brief completion time: 14 days."
   - "Facilitator bottleneck: only 3 available grain inspectors serve the entire SE Asia corridor."
   Can this be packaged as a subscription analytics product for trade agencies or industry associations?

3. **Trade finance integration** — Show a completed Deal Brief to a bank's trade finance desk. "Is this document sufficient to initiate a letter of credit assessment? What's missing?" The bank's feedback refines the Deal Brief template — and tests whether trade finance integration is a viable value-added service.

4. **Compliance and regulatory advisory** — The Knowledge Slot Q&A system can be tested as a standalone advisory service. "If I'm exporting CWRS #1 wheat to Indonesia, what import certifications does the buyer need?" If the answers are reliably authoritative (sourced from the curated reference library), this has standalone value.

5. **Insurance integration** — Present synthetic deal parameters to a cargo insurer. Can they price a policy from the Deal Brief's route, commodity, and value data? What additional data would they need?

6. **Platform UX testing with real service providers** — Have real facilitators (customs brokers, shipping agents, inspectors) use the platform with synthetic principals. Does the facilitator experience work? Can they find and respond to role slot searches? Can they contribute to a Deal Brief?

**What makes this phase distinctive:** The synthetic participants provide the *context* — the deals, the corridors, the commodity flows. But the service providers being tested are *real*. This is an ethical and practical hybrid: no real market participants are deceived (synthetic users are clearly labeled as synthetic), but real service integrations are validated.

**Output:**
- Service integration test results (what works, what needs platform changes)
- Refined Deal Brief templates (incorporating bank/insurer/logistics feedback)
- Market analytics samples (demonstrating subscription product viability)
- Business model validation: which value-added services generate willingness-to-pay?

---

### Phase 8: Market Launch — Synthetic to Real Transition (Sponsor's Responsibility)

This is the point at which the digital twin has served its purpose and the sponsor transitions to building a **real marketplace with real participants**.

> **⚠️ CRITICAL ETHICAL CONSTRAINT:** Synthetic users must **NEVER** coexist with real users in the same marketplace instance. The transition is a **clean cutover**, not a gradual blend. Mixed use would be deceptive to real participants about who they are interacting with and would undermine the trust that the platform exists to build. (See GEMINI.md — Restrictions on use of ClientSynth.)

**The clean cutover protocol:**

1. **Preserve configuration** — The `marketplace.yaml`, prompts, Deal Brief templates, facilitator role definitions, and reference library are carried forward unchanged. These are the sponsor's curated market configuration — they do not depend on synthetic participants.
2. **Archive synthetic data** — All synthetic participant records, synthetic deals, and synthetic Deal Briefs are archived (for analytics reference) and then **removed from the production instance**. The production database starts with zero participants.
3. **Preserve the reference library** — The Knowledge Slot content (reference documents, metadata, embeddings) carries forward. This is sponsor-curated domain knowledge, not synthetic data.
4. **Preserve service integrations** — Any trade finance, logistics, insurance, or analytics integrations tested in Phase 7 carry forward.
5. **Deploy production infrastructure** — The production instance may require different hosting, monitoring, backup, and security configurations than the digital twin sandbox.
6. **Begin real participant recruitment** — This is the sponsor's operational responsibility.

**What the sponsor owns from this point forward:**

| Responsibility              | Description                                                                                                                       | Why it's the sponsor's                                                                                                     |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Participant recruitment** | Marketing, outreach, onboarding campaigns to attract real buyers, sellers, and facilitators                                       | Requires domain-specific go-to-market strategy, industry relationships, and credibility that only the vertical sponsor has |
| **Customer support**        | Responding to participant questions, resolving access issues, handling disputes                                                   | Requires domain expertise and human judgment                                                                               |
| **Content maintenance**     | Keeping the reference library current as regulations change, standards evolve, and new trade agreements emerge                    | Requires ongoing domain monitoring                                                                                         |
| **Platform operations**     | Hosting, monitoring, backups, security, uptime                                                                                    | Standard SaaS operations                                                                                                   |
| **Business development**    | Building relationships with service providers (banks, logistics, insurance), negotiating integration terms                        | Requires commercial relationships                                                                                          |
| **Regulatory compliance**   | Ensuring the platform meets data protection, financial services, and trade compliance requirements in its operating jurisdictions | Jurisdiction-specific legal expertise                                                                                      |

**What DeeperPoint / the Forge continues to provide:**

| Contribution                   | Description                                                                                                      |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| **Framework updates**          | Cosolvent framework improvements, bug fixes, new features — available to all verticals under MIT license         |
| **Architectural guidance**     | Advisory on scaling, new module integration, matching algorithm tuning                                           |
| **New vertical digital twins** | If the sponsor wants to expand to adjacent corridors or new markets, the Forge produces additional digital twins |
| **Knowledge curation support** | AIKnowledgeSlotCuration tooling for updating the reference library                                               |

**Output:**
- Production marketplace instance (zero synthetic users, full configuration)
- Operational handoff documentation
- Ongoing framework support relationship

---

## 5. Human Tasks — What Cannot Be Automated

Even in the matured state, certain tasks require human judgment. These are the irreducible human contributions:

| Task                                | Who                       | Why it cannot be automated                                                                                                                                         | When      |
| ----------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- |
| **Market selection and scoping**    | Sponsor / domain expert   | Requires judgment about which markets have structural desire to exchange, which corridors are commercially viable, and which regulatory environments are navigable | Phase 1   |
| **Reference document curation**     | Domain expert             | Deciding which documents are authoritative, which are current, and which represent the sponsor's intended regulatory posture                                       | Phase 2   |
| **Domain schema review**            | Domain expert             | AI can extract a schema, but only a human can judge whether the extracted vocabulary correctly represents the market's actual terminology and distinctions         | Phase 2   |
| **Marketplace config review**       | Domain expert + architect | Matching prompts and deal term categories require judgment about what matters in this specific market                                                              | Phase 3   |
| **Population plausibility check**   | Domain expert             | Statistical distributions may be correct but culturally implausible; a human must validate that the synthetic population "feels right"                             | Phase 4   |
| **Simulation interpretation**       | Analyst / sponsor         | Determining what the simulation results mean for market viability, which metrics matter, and what story to tell investors                                          | Phase 6   |
| **Demo presentation**               | Sponsor / team            | Walking stakeholders through the prototype and answering questions requires domain expertise and persuasive judgment                                               | Phase 6   |
| **Service integration negotiation** | Sponsor                   | Establishing relationships with banks, logistics providers, insurers, and compliance advisors requires human relationship-building and commercial negotiation      | Phase 7   |
| **Participant recruitment**         | Sponsor                   | Attracting real buyers, sellers, and facilitators requires domain credibility, marketing, and industry relationships                                               | Phase 8   |
| **Cutover decision**                | Sponsor + architect       | Judging when the digital twin has validated enough to justify the investment in real participant recruitment                                                       | Phase 7→8 |

---

## 6. Parametric Effort and Time Estimates

The effort required to build a digital twin varies with market vertical complexity. The following estimates assume the Forge toolchain is operational (all integration points built) and measure the **per-vertical** effort for each new market.

### 6.1 Complexity Dimensions

Market verticals vary along five dimensions that drive effort:

| Dimension                         | Low complexity                     | Medium complexity                      | High complexity                                                   |
| --------------------------------- | ---------------------------------- | -------------------------------------- | ----------------------------------------------------------------- |
| **Participant types**             | 2 (buyer + seller)                 | 3–4 (+ 1–2 facilitator types)          | 5+ (multiple facilitator types, aggregators, inspectors)          |
| **Regulatory jurisdictions**      | Single country                     | 2–3 countries, one trade agreement     | 5+ countries, multiple overlapping agreements                     |
| **Product/service heterogeneity** | Commodity (few quality dimensions) | Semi-differentiated (10–20 attributes) | Highly differentiated (50+ attributes, subjective quality)        |
| **Reference document volume**     | 5–15 documents                     | 15–50 documents                        | 50–200+ documents                                                 |
| **Deal structure complexity**     | Simple (price + quantity)          | Multi-issue (5–8 negotiable terms)     | Complex (10+ terms, contingent on facilitator roles, multi-stage) |

### 6.2 Complexity Tiers

| Tier                  | Example verticals                                                                                              | Complexity profile                                                               |
| --------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| **Tier 1 — Simple**   | Local farmers' market, peer-to-peer equipment rental, single-commodity domestic trade                          | 2 types, 1 jurisdiction, commodity, <15 docs, simple deals                       |
| **Tier 2 — Moderate** | Cross-border grain trade (single corridor), specialty manufacturing B2B, professional services marketplace     | 3–4 types, 2–3 jurisdictions, semi-differentiated, 15–50 docs, multi-issue deals |
| **Tier 3 — Complex**  | Multi-corridor agricultural trade, cross-border healthcare services, defense procurement, art and collectibles | 5+ types, 5+ jurisdictions, highly differentiated, 50+ docs, complex deals       |

### 6.3 Per-Vertical Effort — Phases 1–6: Digital Twin Prototype (with operational Forge)

These estimates cover **human-hours of skilled effort**, not elapsed time. They assume one domain expert and one technical integrator are available.

| Phase                                  | Tier 1 (Simple) | Tier 2 (Moderate) | Tier 3 (Complex) |
| -------------------------------------- | --------------- | ----------------- | ---------------- |
| **Phase 1: Market Description**        | 4–8 hrs         | 8–16 hrs          | 16–40 hrs        |
| **Phase 2: Knowledge Curation**        | 8–16 hrs        | 24–48 hrs         | 60–120 hrs       |
| **Phase 3: Marketplace Configuration** | 4–8 hrs         | 12–24 hrs         | 24–60 hrs        |
| **Phase 4: Population Synthesis**      | 4–8 hrs         | 8–16 hrs          | 16–40 hrs        |
| **Phase 5: Assembly & Deployment**     | 2–4 hrs         | 4–8 hrs           | 8–16 hrs         |
| **Phase 6: Simulation & Demo**         | 8–16 hrs        | 16–32 hrs         | 32–80 hrs        |
| **Subtotal (Phases 1–6)**              | **30–60 hrs**   | **72–144 hrs**    | **156–356 hrs**  |
| **Elapsed time (1 person)**            | **1–2 weeks**   | **2–4 weeks**     | **4–9 weeks**    |
| **Elapsed time (2 people)**            | **3–5 days**    | **1–3 weeks**     | **3–6 weeks**    |

### 6.4 Per-Vertical Effort — Phase 7: Business Design Validation

Phase 7 effort depends heavily on which value-added services the sponsor wants to pretest and how many external service providers are involved. The following estimates assume the digital twin from Phases 1–6 is operational.

| Service integration                      | Tier 1 (Simple)  | Tier 2 (Moderate) | Tier 3 (Complex) |
| ---------------------------------------- | ---------------- | ----------------- | ---------------- |
| **Sample fulfillment test (1 corridor)** | 8–16 hrs         | 16–32 hrs         | 32–60 hrs        |
| **Market analytics prototype**           | 8–16 hrs         | 16–40 hrs         | 40–80 hrs        |
| **Trade finance integration test**       | N/A (too simple) | 16–32 hrs         | 32–60 hrs        |
| **Compliance advisory test**             | 4–8 hrs          | 8–24 hrs          | 24–60 hrs        |
| **Insurance integration test**           | N/A              | 8–16 hrs          | 16–40 hrs        |
| **Facilitator UX testing**               | N/A              | 16–32 hrs         | 32–60 hrs        |
| **Phase 7 subtotal (typical scope)**     | **16–32 hrs**    | **48–120 hrs**    | **120–300 hrs**  |
| **Elapsed time**                         | **1–2 weeks**    | **3–6 weeks**     | **6–12 weeks**   |

**Notes on Phase 7 estimates:**
- These include only the *technical* work of integration testing, not the *commercial* work of establishing relationships with service providers (which is the sponsor's responsibility and is highly variable).
- Sample fulfillment involves coordinating a real physical shipment — elapsed time is dominated by logistics, not engineering.
- Trade finance integration requires engaging with a bank's trade finance desk, which may have its own timeline.
- Phase 7 can run **selectively** — the sponsor need not test all services. A minimum viable Phase 7 tests only market analytics and one service integration.

### 6.5 Per-Vertical Effort — Phase 8: Market Launch

Phase 8 is fundamentally different from Phases 1–7. The Forge's *technical* contribution is modest — it's mostly a clean deployment operation. The dominant effort is the sponsor's *business operations*: recruitment, marketing, support, and ongoing operations.

| Task                                          | Forge / technical effort | Sponsor / business effort           |
| --------------------------------------------- | ------------------------ | ----------------------------------- |
| **Clean cutover (archive synthetic, deploy)** | 8–16 hrs                 | —                                   |
| **Production infrastructure setup**           | 16–40 hrs                | —                                   |
| **Operational handoff documentation**         | 8–24 hrs                 | Review: 8–16 hrs                    |
| **Participant recruitment**                   | —                        | **Ongoing, 3–12+ months**           |
| **Customer support setup**                    | —                        | 40–80 hrs initial + ongoing         |
| **Marketing and outreach**                    | —                        | **Ongoing, sponsor-funded**         |
| **Regulatory/legal compliance**               | —                        | 40–200 hrs (jurisdiction-dependent) |
| **Phase 8 technical subtotal**                | **32–80 hrs**            |                                     |
| **Phase 8 sponsor subtotal**                  |                          | **Variable — see below**            |

**Sponsor effort in Phase 8 is not meaningfully parameterizable** by market complexity tier. It depends on:
- The sponsor's existing industry relationships and reputation
- The target participant pool size and geographic distribution
- Regulatory requirements in operating jurisdictions
- The sponsor's marketing budget and capabilities
- Whether the sponsor is a known industry body (faster recruitment) or a new entrant (slower)

As a rough guide: a trade commission launching a marketplace for its existing member base can begin generating real activity in 3–6 months. A new entrant building a participant base from scratch should plan for 6–18 months to reach minimum viable market thickness.

### 6.6 Full Lifecycle Summary

| Lifecycle stage                                  | Tier 2 (Moderate) effort | Elapsed time   | Primary responsibility |
| ------------------------------------------------ | ------------------------ | -------------- | ---------------------- |
| **Phases 1–6: Digital Twin Prototype**           | 72–144 hrs               | 1–4 weeks      | Forge + domain expert  |
| **Phase 7: Business Design Validation**          | 48–120 hrs               | 3–6 weeks      | Sponsor + Forge        |
| **Phase 8: Market Launch (technical)**           | 32–80 hrs                | 1–2 weeks      | Forge                  |
| **Phase 8: Market Launch (business operations)** | Sponsor-funded           | 3–18 months    | Sponsor                |
| **Total technical effort (Forge)**               | **152–344 hrs**          | **5–12 weeks** | Forge                  |

The Forge's involvement tapers as the lifecycle progresses. By Phase 8, the Forge's role is limited to framework support, architectural guidance, and (optionally) producing digital twins for adjacent verticals.

### 6.7 Key Assumptions Behind These Estimates

1. **Forge toolchain is operational.** The integration points in §3 are built and working. Without the Forge, each phase requires substantially more manual work (multiply by 3–5×).
2. **Domain expert is available.** Phases 1, 2, 3, and 6 require someone who knows the market. Without domain expertise, these phases cannot be completed — AI cannot substitute for judgment about which regulations matter, which participant types exist, or what a plausible trade corridor looks like.
3. **Reference documents exist.** The estimate assumes the sponsor has or can procure the reference materials. If reference documents must be researched and sourced from scratch, add 20–60 hours for Tier 2 and 40–120 hours for Tier 3.
4. **No custom code.** These estimates assume the Cosolvent framework, ClientSynth, and AIKnowledgeSlotCuration handle the vertical without code changes — only configuration, prompts, and content. Custom code for vertical-specific features (e.g., cold chain modeling, specialized compliance checks) would be additional.
5. **The effort curve flattens.** The first vertical built on the Forge will be slower as the workflow is refined. Subsequent verticals benefit from templates, reusable prompts, and operational muscle memory. Expect the second vertical to take 60–70% of the first, and the third to take 40–50%.

### 6.8 What the Estimates Do NOT Include

| Excluded item                               | Why                                                                    | Approximate additional effort |
| ------------------------------------------- | ---------------------------------------------------------------------- | ----------------------------- |
| Building the Forge toolchain itself         | One-time infrastructure, covered in individual roadmaps                | See §7                        |
| UI/UX design for vertical-specific frontend | Requires Conflict C5 resolution (cosolvent-beta is currently headless) | 80–200 hrs per vertical       |
| Sponsor's business operations (Phase 8)     | Ongoing cost driven by market size, not technical complexity           | Sponsor-funded                |

---

## 7. Building the Forge Itself — One-Time Infrastructure

Before the per-vertical workflow in §6 can operate, the integration infrastructure must be built. This is a one-time investment.

| Integration component                                       | Effort estimate | Dependencies                 | Roadmap reference           |
| ----------------------------------------------------------- | --------------- | ---------------------------- | --------------------------- |
| AIKnowledgeSlotCuration → `reference_library` output format | 1–2 weeks       | AIKSC Phase 3                | AIKSC ROADMAP §5            |
| `reference_library` table + metadata-filtered vector search | 2–3 weeks       | Cosolvent Phase 1            | Cosolvent ROADMAP §16.2     |
| Domain schema → `marketplace.yaml` generator                | 2–3 weeks       | Domain schema format spec    | **New work**                |
| ClientSynth C0 — file-based Cosolvent export                | 1 week          | Export format spec           | ClientSynth ROADMAP §C0     |
| ClientSynth C1.1 — MarketDefinition import                  | 1–2 weeks       | marketplace.yaml spec        | ClientSynth ROADMAP §C1     |
| **Domain schema → ClientSynth vocabulary constraints**      | 1–2 weeks       | Domain schema format spec    | **New work**                |
| Deal entity + Deal State Machine                            | 3–4 weeks       | Conflict C1 resolution       | Cosolvent ROADMAP §1.8–1.11 |
| Handoff Artifact / Deal Brief generator                     | 2–3 weeks       | Deal entity                  | Cosolvent ROADMAP §1.11     |
| Simulation runner + analytics                               | 2–3 weeks       | Deal entity, matching engine | **New work**                |
| End-to-end orchestration (CLI or script)                    | 1–2 weeks       | All above components         | **New work**                |
| **Total one-time infrastructure**                           | **16–25 weeks** |                              |                             |

This estimate overlaps substantially with the phased roadmaps already documented — Phases 0, 1, and parts of Track A and Track B in `cosolvent-beta/ROADMAP.md`. The Forge does not add much new work beyond what was already planned; it primarily adds the **three missing connectors** (§3.2) and the orchestration layer.

---

## 8. Strategic Packaging — How the Forge Maps to Business Models

The strategic packaging document (`CosolventAI/docs/session-notes/2026-02-18-strategic-packaging.md`) identifies five models. The Forge is most directly relevant to three of them. The mapping is explicit:

### Model 2: Sponsored First Vertical

**How the Forge changes the pitch:**

Without the Forge, Model 2 requires the sponsor to fund both framework development and vertical-specific work simultaneously. The pitch is "fund us while we build the infrastructure AND your marketplace."

With the Forge, the pitch becomes:

> *"The infrastructure exists. Here is a working digital twin of your market — built from your own reference documents, populated with realistic synthetic participants, demonstrating matching, deal assembly, and Deal Brief generation. Your $100K development budget goes toward production deployment and real participant recruitment — not R&D."*

**Per-vertical cost implications (from §6.3):**

| Sponsor tier | Human-hours | Approximate cost at $150/hr blended | What the sponsor gets                             |
| ------------ | ----------- | ----------------------------------- | ------------------------------------------------- |
| Tier 1       | 30–60 hrs   | $4,500–$9,000                       | Working digital twin, simple market               |
| Tier 2       | 72–144 hrs  | $10,800–$21,600                     | Working digital twin, moderate complexity         |
| Tier 3       | 156–356 hrs | $23,400–$53,400                     | Working digital twin, complex cross-border market |

These are **pre-production** costs — what it takes to produce the digital twin prototype. Production deployment (hosting, CI/CD, monitoring, support) and participant recruitment are additional and are the sponsor's operational responsibility.

**Key selling point:** The digital twin is the demo. The sponsor does not have to imagine what their marketplace will look like — they can click through it.

### Model 3: Academic Partnership

**How the Forge changes the pitch:**

The Forge transforms a "build a marketplace" research project into a **"run experiments on market physics"** research platform — a much better fit for academic incentives.

> *"Here is a research platform that lets graduate students build digital twins of thin markets, run controlled experiments on market physics (opacity, distance, information density, cold start), and publish quantitative results. The thesis is already written (Chapters 2–8 of the whitepaper). The tooling already exists. The student's contribution is the empirical validation."*

**Academic use-case mapping (from whitepaper Chapter 35, Use 2):**

| Research question                                                    | Digital Twin experiment                                                                                                                                                    | Thesis potential                                          |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| "How does opacity reduction affect market thickness?"                | Generate two populations with identical structure; reduce opacity in one (add quality certifications to all profiles). Compare match rates, deal completion, time-to-deal. | Strong — quantitative comparison with controlled variable |
| "What is the cold start threshold for a cross-border grain market?"  | Run simulations with populations of 20, 50, 100, 200, 500 participants. Identify the population at which match quality stabilizes.                                         | Strong — parametric analysis with clear methodology       |
| "Do asynchronous brokerage agents reduce temporal distance effects?" | Compare deal completion rates and elapsed times between agent-assisted and human-only simulation runs across time zones.                                                   | Strong — controlled experiment with measurable outcomes   |
| "How does facilitator availability affect deal assembly?"            | Vary the number and type of facilitator role slots. Measure deal completion rates when logistics providers are scarce vs. abundant.                                        | Strong — directly tests market physics hypothesis         |

**Student project scoping (from §6.3):**

A Tier 2 digital twin (72–144 hours) maps well to a single-semester graduate project. The student builds one vertical's digital twin, runs one class of experiments, and writes up the results. The domain expert (you) provides the reference documents and reviews the domain schema. The student handles Phases 2–6.

### Model 4: Founder / Startup Partnership

**How the Forge changes the pitch:**

The Forge gives the founder something founders prize above all else: **a repeatable, scalable delivery mechanism.** The founder does not just inherit a framework — they inherit a production line for digital twins.

> *"Here is infrastructure that lets you build a working market prototype for any thin market vertical in 1–4 weeks. Your business model is manufacturing digital twins: charge sponsors $15K–$50K for a Tier 2/3 prototype, then $5K–$15K/month for managed hosting. At 4–6 verticals per year, you have a $200K–$600K revenue business from prototypes alone — before production deployments, managed hosting, or market intelligence revenue."*

**Revenue model mapping (from strategic packaging §Revenue Models):**

| Revenue stream                                  | How the Forge enables it                                                        | Estimated unit economics                                                                            |
| ----------------------------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **Digital twin prototyping (services)**         | Forge produces the prototype in 1–4 weeks                                       | Charge $15K–$50K; cost $5K–$20K in labor; 50–75% gross margin                                       |
| **Managed deployments (SaaS)**                  | Prototype → production deployment for sponsors who want to go live              | $5K–$15K/month recurring; hosting cost ~$500–$2K/month                                              |
| **Vertical customization (services → product)** | Domain schemas and prompts become reusable templates across similar verticals   | Second vertical in a sector (e.g., different trade corridor) takes 40–50% of first; margin improves |
| **Market intelligence (long-term)**             | Digital twin analytics generate market structure data that has standalone value | Subscription analytics; requires multiple deployed verticals generating data                        |

**The compounding economics:** Each vertical built on the Forge produces reusable artifacts:
- Domain schemas that inform adjacent verticals
- Prompt templates that transfer across similar markets
- Population generation patterns that can be adapted
- Matching and deal configuration templates

The third agricultural-trade vertical costs 40% of the first. The sixth costs 25%. This is a classic platform economics curve.

---

## 9. The Effort Curve — How Cost Declines with Experience

```
Per-vertical effort (indexed to first vertical = 100)

     100 ┤ ■ First vertical
         │
      80 ┤
         │
      65 ┤     ■ Second vertical (same sector)
         │
      50 ┤
         │
      40 ┤         ■ Third vertical (same sector)
         │
      30 ┤             ■ Fourth vertical (adjacent sector)
         │
      25 ┤                 ■ Fifth+ vertical
         │
         └──────────────────────────────────
```

**Why it flattens:**
- Domain schemas share structural patterns across similar verticals
- Prompts transfer with minor tuning
- Population generation patterns are parameterizable rather than recreated
- Operational processes are documented and repeatable
- The reference library for adjacent verticals partially overlaps (same trade agreements, overlapping regulatory frameworks)

**Cross-sector transitions** (e.g., agricultural trade → mental health services) reset the curve partially — participant types, deal structures, and regulatory environments are different. But the tooling, process, and configuration infrastructure remain the same. Expect a cross-sector first vertical to cost 60–70% of the very first vertical ever built.

---

## 10. Forge Readiness — What Needs to Happen and in What Order

### Prerequisites (one-time, sequential dependencies)

```
Week 1–2:   Conflict C1 resolution (JSONB vs relational)
              │
Week 2–5:   Deal entity + Deal State Machine
              │
Week 3–5:   reference_library table + metadata search   (parallel track)
              │
Week 5–7:   Handoff Artifact generator
              │
Week 4–6:   Domain schema format specification          (parallel track)
              │
Week 6–8:   Domain schema → marketplace.yaml generator
              │
Week 6–8:   Domain schema → ClientSynth vocabulary      (parallel track)
              │
Week 7–9:   ClientSynth C0 (file-based export)
              │
Week 8–10:  ClientSynth C1.1 (MarketDefinition import)
              │
Week 9–11:  AIKSC → reference_library output format
              │
Week 10–12: Simulation runner + analytics
              │
Week 12–14: End-to-end orchestration + first vertical test
              │
Week 14–16: First complete digital twin (Tier 2, grain trade)
```

This timeline assumes one developer working full-time on Cosolvent and part-time contributions on ClientSynth and AIKSC. With two developers, the parallel tracks compress and the total drops to 10–12 weeks.

### The first vertical as proof

The first digital twin should be **Tier 2, agricultural grain trade (Canada → Southeast Asia)**:
- Reference materials are already partially curated in AIKnowledgeSlotCuration (GAFTA contracts, CGC grading standards)
- The market is well-understood from the whitepaper's case studies
- The domain expert (you) knows this market intimately
- It maps directly to the GPSim reference demo identified in the strategic packaging document

---

## 11. Risk Register

| Risk                                                  | Impact                                                              | Mitigation                                                                                                                   |
| ----------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Conflict C1 not resolved cleanly**                  | Blocks Deal entity, delays everything downstream                    | Resolve first; the hybrid approach (typed tables + JSONB metadata) is the recommendation                                     |
| **Domain schema format is underspecified**            | Produces marketplace configs that don't match real market structure | Build the first domain schema by hand for grain trade, then extract the format pattern                                       |
| **ClientSynth generates implausible populations**     | Undermines demo credibility                                         | Build domain vocabulary constraints before attempting first vertical; human review in Phase 4                                |
| **Single-developer bottleneck**                       | Timeline extends; all tracks are sequential                         | All three repos are MIT-licensed and documented; a partner developer can contribute to any                                   |
| **Sponsor expects production system, gets prototype** | Relationship damage                                                 | Clear positioning: the digital twin is a demonstration tool, not a production marketplace. Production deployment is Phase D. |
| **Academic partner's timeline too slow**              | Momentum lost                                                       | Academic track runs in parallel with other models, not as sole strategy                                                      |

---

## 12. Relationship to Whitepaper Concepts

| Whitepaper concept (Chapter)             | Forge implementation                                                                                                            |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Three uses of Digital Twins (Ch. 35)** | Phase 6 covers all three: testing automation design (Use 1), validating market physics (Use 2), demonstrating viability (Use 3) |
| **Cold start problem (Ch. 27, 34)**      | ClientSynth-generated populations bypass the cold start entirely for prototyping                                                |
| **Market physics parameters (Ch. 2–8)**  | Domain schema captures market characteristics; simulation reveals which physics dominate                                        |
| **Trusted intermediary (Ch. 21)**        | Matching engine in Cosolvent implements confidential matching; digital twin demonstrates it                                     |
| **Handoff Artifact (Ch. 33)**            | Deal Brief generator produces the platform's primary deliverable. Phase 7 validates it with real service providers.             |
| **Framework generalization (Ch. 32)**    | The Forge IS the generalization — marketplace.yaml per vertical, not hardcoded schemas                                          |
| **Feedback loop (Ch. 35)**               | Digital twin (Phases 1–6) → business validation (Phase 7) → real market (Phase 8) → collect real data → recalibrate → iterate   |
| **Fulfillment & Settlement (Ch. 13)**    | Phase 7 sample fulfillment testing validates whether the Deal Brief drives real-world logistics                                 |

---

## 13. Success Criteria

The Forge is operational when the following are demonstrated end-to-end:

1. ☐ A market description + reference documents produce a validated `domain_schema.yaml`
2. ☐ The domain schema generates a complete `marketplace.yaml` that compiles without error
3. ☐ ClientSynth generates a population of 50+ participants conforming to the marketplace schema, using domain-appropriate vocabulary
4. ☐ The reference library is loaded and queryable from a participant's perspective (metadata-filtered vector search returns relevant results)
5. ☐ Semantic matching produces plausible buyer-seller pairs from the synthetic population
6. ☐ A deal can be initiated, negotiated through the issue-level state machine, facilitator roles resolved, and a Deal Brief generated
7. ☐ A non-technical stakeholder can walk through the prototype and understand the market it represents

---

## 14. Open Questions

1. **Should the orchestration layer live in its own repo?** Arguments for: clean separation of concerns, independent release cycle. Arguments against: another repo to maintain, the orchestration is thin and mostly configuration.

2. **Should the domain schema format be a standard?** If the Forge produces digital twins for multiple verticals, the domain schema YAML becomes a de facto standard for describing thin markets. Is it worth formalizing (and potentially publishing as a contribution alongside the whitepaper)?

3. **What is the minimum viable simulation?** Phase 6 ranges from "browse and match" (relatively simple) to "full deal negotiation with agent-assisted asynchronous flow" (requires most of Track A). What is the minimum that constitutes a convincing demo for each strategic model?

4. **How does the Forge relate to GPSim?** The GPSim repo was identified as the reference demo vehicle. Does the Forge subsume GPSim, or does GPSim remain a separate, thinner demonstration tool?

5. **What is the minimum viable Phase 7?** The sponsor could test all six service integration types or just one. A plausible minimum is market analytics + one physical service test (sample fulfillment or trade finance). What is the minimum that convinces the sponsor to commit to Phase 8?

6. **How should the cutover be staged for large populations?** The clean cutover protocol (§4, Phase 8) assumes the synthetic population is removed entirely before real participants are onboarded. For very large markets, should the cutover be staged by participant type (e.g., onboard real facilitators first, then sellers, then buyers)? The ethical constraint (no mixing) still applies — it means sequential rollout with clear separation, not blending.

7. **What analytics from Phase 7 should be preserved across the cutover?** The synthetic population generates market structure data (match density, corridor traffic, facilitator demand patterns) that has analytical value even after the synthetic users are retired. Should this be preserved as a "baseline" dataset that the production analytics can be compared against?
