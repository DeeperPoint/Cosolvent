# What Is Cosolvent?

Cosolvent is a backend platform for building B2B marketplace MVPs. It targets a specific class of problem: the **thin market** — a market where buyers and sellers exist, but useful trades still fail.

## The Thin-Market Problem

```
Market function requires: Desire > Opacity + Friction
```

In thin markets, intent is present but execution is fragile:
- participants are sparse or fragmented across channels
- information is complex and hard to compare across profiles
- trust is expensive to establish without structured workflows
- timing between counterparties rarely aligns
- regulatory and workflow friction blocks momentum

Cosolvent focuses on the right side of that equation — reducing opacity and friction through guided setup, deterministic generation, and runtime policy enforcement.

## What You Can Build

Cosolvent is suited for **B2B marketplaces** where:
- participants need vetting (approval workflows, document upload)
- profiles are structured but heterogeneous across roles
- search must combine keyword and semantic matching
- contact must follow defined rules (who contacts whom, with approval)

Examples:
- Agricultural commodity trading (producers → buyers)
- Professional services matching (providers → clients)
- Parts and materials sourcing (manufacturers → buyers)
- Specialty finance or investment introductions

## Key Concepts

### marketplace.yaml
The single source of truth. Defines your marketplace's identity, participant roles, profile schemas, onboarding workflows, communication rules, and discovery behavior. The platform compiles it into deployable artifacts.

### Participant types
Every marketplace has 2–3 participant types (e.g. Producer, Buyer). Each type has a role (`supply`, `demand`, or `facilitator`), permission flags, and a profile schema.

### Profiles
Profiles are the core marketplace entity. A user registers as a participant type, fills a draft, and submits for approval. Approved profiles are active and discoverable. Profiles double as listings — there is no separate listing entity.

### Onboarding and approval
Each participant type has configurable onboarding rules: required completeness threshold, document upload, AI-assisted profile generation, and admin approval. Approval can be manual (human review) or auto.

### Discovery
Search combines keyword matching with vector similarity (when AI is configured). Results are filtered by visibility tier: anonymous users see public fields, authenticated users see protected fields, owners and admins see all fields.

### Communication rules
Who can contact whom, and whether the receiver must accept before a conversation begins. Rules are defined per pair of participant types.

### The compiler
Your `marketplace.yaml` is compiled into Python modules, database migrations, and an OpenAPI spec. Generated artifacts live in managed zones and are never hand-edited.

## How to Get Started

If you want to run Cosolvent with Docker in under 10 minutes:

→ [Quick Start](quick-start.md)

If you want to understand the setup wizard in detail:

→ [Setup Wizard](setup-wizard.md)

If you want to understand every config option:

→ [Marketplace Config Reference](marketplace-config.md)

## See Also
- [Quick Start](quick-start.md) — clone to running marketplace in 5 steps
- [Setup Wizard](setup-wizard.md) — full wizard walkthrough
- [Marketplace Config Reference](marketplace-config.md) — every YAML field explained
