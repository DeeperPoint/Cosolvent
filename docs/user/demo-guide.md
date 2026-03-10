# Demo Guide

Cosolvent supports several approaches to demonstrating a marketplace, from quick developer walkthroughs to a publicly shareable, read-only instance that costs nothing per visitor. This guide covers what is available, what is planned, and how the pieces fit together.

## Demo Options at a Glance

| Approach | Audience | Cost per visit | Data required | Implementation status |
|----------|----------|---------------|---------------|----------------------|
| **Local walkthrough** | Developer / technical evaluator | None (runs locally) | Example config or your own `marketplace.yaml` | ✅ Available now |
| **Recorded walkthrough** | Investors, partners, non-technical stakeholders | None | Pre-recorded video or screenshots | Can be produced from any running instance |
| **Read-only Demo Mode** | General public, website visitors, trade-show attendees | **Zero** | Synthetic population + pre-computed results | 🔲 Planned (see below) |
| **Controlled live demo** | Scheduled investor meetings, trade-show booths with staff | Low (limited live LLM queries) | Synthetic population + live AI backend | 🔲 Planned (optional enhancement) |

## Local Walkthrough (Available Now)

Any running Cosolvent instance can be used as a demo. The [Quick Start](quick-start.md) gets you from clone to running in about 10 minutes:

```bash
git clone https://github.com/DeeperPoint/Cosolvent.git
cd Cosolvent
cp .env.example .env
# Edit .env with your settings
make setup-up        # Start the onboarding UI
make compile         # Generate artifacts from marketplace.yaml
make up              # Start the full stack
```

Browse to `http://localhost:18080/onboarding` for the setup wizard, or `http://localhost:18000/docs` for the API documentation.

This is the fastest way to evaluate the platform and is suitable for technical audiences who can run Docker locally.

---

## Read-Only Demo Mode (Planned)

This is the "cheap to operate" demo referenced in the [Cosolvent roadmap](../../Cosolvent-ROADMAP.md) and specified in detail in the [Convergence design document](../../CONVERGENCE.md) (Phase 6a).

### Concept

A read-only Cosolvent instance that can be deployed publicly — linked from a website, shared on social media, or embedded in a pitch deck — with **zero marginal cost per visitor** and no risk of abuse.

Visitors are assigned a synthetic persona and explore the marketplace from that participant's perspective. All results are pre-computed; no live LLM calls are made. The visitor experience looks and feels identical to a live marketplace, but every query returns cached content.

### How It Works

Demo Mode has two components: an **admin switch** and a **visitor onboarding flow**.

#### Admin Mode Switch

An administrative toggle puts the entire instance into demo mode:

| Setting | Live mode (default) | Demo mode |
|---------|--------------------:|-----------|
| **Database writes** | Allowed | **Blocked** — all data is read-only |
| **User-initiated LLM prompts** | Allowed | **Blocked** — only curated prompt buttons, returning pre-computed results |
| **Authentication** | Full login | **Persona assignment only** — visitors get a synthetic identity, not a real account |
| **Data persistence** | Normal | **None** — visitor sessions are ephemeral; nothing is saved |
| **Admin access** | Full admin panel | Admin panel remains accessible (password-protected) for toggling mode and updating content |

#### Visitor Onboarding

When a visitor arrives at a demo-mode instance:

1. **Role selection** — The visitor chooses a participant type (e.g., "Explore as a Grain Exporter" or "Explore as a Mill/Processor").
2. **Persona assignment** — The system randomly assigns a synthetic participant of that type. The visitor sees the persona's profile, pre-computed match gallery, and marketplace view.
3. **Guided exploration** — At each screen, curated "Ask about this" buttons replace free-form input. Each button returns a pre-computed answer.
4. **Session end** — When the visitor leaves, the session evaporates. No data is collected, no cookies persist, no account is created. Returning visitors can be assigned a different persona.

#### Pre-Computation Layer

A one-time pre-computation step generates all cached results before the demo goes live:

| Artifact | Source |
|----------|--------|
| Match results per persona | pgvector semantic matching for every synthetic participant |
| Match rationale per pair | LLM-generated explanation for each top-N match |
| Sample Deal Briefs | Completed deals per participant type with full handoff content |
| Knowledge Slot Q&A | Curated questions per participant type, answered against the reference library |
| Facilitator search results | Pre-computed recommendations for each deal type/corridor |
| Market analytics | Aggregate statistics: match density, corridor traffic, facilitator utilization |
| Peer comparisons | Profile comparisons within each participant type |

**Estimated one-time cost:** For a population of 100 synthetic participants with 10 curated prompts each, approximately 1,000 LLM calls — roughly $5–$50 depending on the model. After that, every visitor interaction is a cache lookup at zero cost.

### Why This Design

The read-only approach solves three problems simultaneously:

1. **Cost control** — Zero marginal cost per visitor. The demo can be linked publicly without worrying about LLM bills.
2. **Security** — No prompt injection risk, no data exfiltration risk, no write access to any database. The worst a malicious visitor can do is click buttons and read pre-computed content.
3. **Multi-perspective demonstration** — Different visitors see different sides of the same market. Someone who selects "Grain Exporter" and someone who selects "Mill/Processor" experience the same marketplace from opposite perspectives, implicitly demonstrating multi-sided matching.

### Prerequisites

Demo Mode depends on several components:

- **Synthetic population** — Generated by [ClientSynth](https://github.com/DeeperPoint/ClientSynth), which produces realistic participant profiles conforming to `marketplace.yaml` schemas. Synthetic profiles are marked with `is_synthetic: true` and are never mixed with real user data.
- **Frontend** — A user-facing interface for gallery browsing, profile viewing, and deal exploration. Cosolvent is currently a headless backend; a frontend is needed for any visual demo.
- **Pre-computation pipeline** — The tooling to run all matching, rationale generation, and Q&A against the synthetic population and cache the results.
- **Demo mode toggle** — The admin switch that puts the instance into read-only mode.

### Implementation Status

Demo Mode is part of the Phase 6a milestone in the [Convergence design document](../../CONVERGENCE.md). The estimated timeline to a demo-ready state is **14–20 weeks** from the start of active development, reflecting the strong foundation already in place (YAML compilation, dynamic profiles, three-tier visibility, AI onboarding, vector search, admin oversight, and communication are all built).

---

## Controlled Live Demo (Planned Enhancement)

As an optional enhancement to Demo Mode, a small number of **live LLM queries per session** (e.g., 3 "ask anything" questions) can be enabled behind a gate such as a captcha, email capture, or access code. This lets the visitor ask their own question and receive a real, contextual answer — dramatically more impressive than pre-computed results.

This reintroduces cost and abuse risk, so it is designed for controlled contexts only: scheduled investor walkthroughs, trade-show booths with staff present, or gated access links.

---

## Further Reading

- [Convergence Design Document](../../CONVERGENCE.md) — Phase 6 and Phase 6a contain the full demo specification
- [Cosolvent Roadmap](../../Cosolvent-ROADMAP.md) — Implementation timeline and phasing
- [Web Roadmap](../../webroadmap.md) — Overview of development phases
- [ClientSynth Integration Notes](../clientsynth-cosolvent-integration-notes.md) — Synthetic population generation for testing and demos

---

[← Back to User Docs](index.md)
