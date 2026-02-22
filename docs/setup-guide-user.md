# Setup Guide for Founders

This guide walks you through configuring your marketplace from scratch using the onboarding wizard. No code or terminal required — everything happens in the browser.

## Opening the wizard

Start the setup service and open the wizard in your browser:

```
http://localhost:18080/onboarding
```

You'll land on the intro screen.

![Intro screen with "Start setup" button](screenshots/placeholder-intro.png)

Click **Start setup** to enter the 7-step wizard.

---

## Step 1 — Choose a starting template

Pick the template closest to your marketplace. This pre-fills every subsequent step with sensible defaults so you only need to adjust what matters.

![Template selection with three preset cards](screenshots/placeholder-step1-templates.png)

| Template | Supply-side | Demand-side | Best for |
|----------|------------|-------------|----------|
| Agriculture | Producer | Buyer | Crop exchanges, farm-to-buyer |
| B2B Services | Service Provider | Client | Professional services matching |
| Manufacturing | Manufacturer | Buyer | Parts, materials sourcing |

After choosing a template you can also tune two quick-answer dropdowns:

- **Team readiness** — `Lean` lowers approval thresholds, `Compliance-heavy` raises them.
- **Launch style** — `Fast MVP` auto-approves demand-side roles, `Curated` adds document requirements for supply-side roles.

These apply broad defaults that you can fine-tune in later steps.

---

## Step 2 — Marketplace basics

Fill in your marketplace's identity. These appear in exports, admin panels, and generated documentation.

![Three fields: name, industry, description](screenshots/placeholder-step2-basics.png)

| Field | Example | Notes |
|-------|---------|-------|
| **Name** | AgriExchange | Your brand name |
| **Industry** | Specialty Agriculture | The vertical you operate in |
| **Description** | Connects small-batch producers with wholesale buyers | One sentence about what your marketplace does |

---

## Step 3 — Roles and capabilities

Define who participates. Every marketplace needs at least two roles (e.g. a supply side and a demand side). You can add a third facilitator role if needed.

![Role cards with permission checkboxes](screenshots/placeholder-step3-roles.png)

For each role you configure:

- **Name** — display name shown to users (e.g. "Producer").
- **Slug** — a short identifier used internally (e.g. `producer`). Changing a slug later updates all references automatically, but avoid changing it after you've generated your project.
- **Role type** — supply-side, demand-side, or facilitator.
- **Permissions** — toggle what this role can do:

| Permission | What it means |
|-----------|---------------|
| Can publish listings | Role can create public listings |
| Can search profiles | Role can run discovery searches |
| Can start conversations | Role can initiate contact |
| Can receive conversations | Role can be contacted by others |
| Can share private files | Role can attach documents in conversations |
| Must complete onboarding | Role must finish profile before accessing the platform |
| Needs approval before active | Admin must approve the profile |
| Visible in search | Profile shows up in search results |

> **Tip:** Keep 2–3 roles for MVP. More roles add complexity to permissions and communication rules.

---

## Step 4 — Onboarding and approval rules

Set the trust and verification standards for each role. This controls what happens when a new user signs up.

![Onboarding cards per role with approval settings](screenshots/placeholder-step4-onboarding.png)

| Setting | What it does |
|---------|-------------|
| **Require admin approval** | New profiles need a manual review before going live |
| **Approval style** | `Manual review` = human checks each profile; `Auto approve` = instant |
| **Minimum completeness** | Profile must be N% filled before submitting (0–100) |

Expand **Advanced onboarding options** for:

- **Require documents on onboarding** — users must upload files (certifications, licenses, etc.).
- **Enable AI extraction from documents** — the system reads uploaded documents and pre-fills profile fields.
- **Enable AI profile drafts** — the system generates a draft profile from uploaded content.
- **Send welcome email when approved** — automatic notification on approval.

> **Recommendation:** Require approval for supply-side roles. Auto-approve demand-side roles for faster activation.

---

## Step 5 — Communication rules

Define who can contact whom. Without rules, users cannot send messages.

![Communication rule cards with initiator/receiver selects](screenshots/placeholder-step5-communication.png)

Each rule specifies:

- **Initiator** — the role that starts the conversation.
- **Receiver** — the role that receives the request.
- **Requires approval** — the receiver must accept before the conversation begins.

Click **Add Communication Rule** to create additional rules.

> **Example:** A buyer initiates contact with a producer, and the producer must accept the request.

---

## Step 6 — Profile fields and discovery

This step has two sections: **Discovery** (how users find each other) and **Profile schema** (what profile data each role has).

### Discovery

![Discovery settings with searchable roles and filter options](screenshots/placeholder-step6-discovery.png)

| Setting | What it controls |
|---------|-----------------|
| **Searchable roles** | Which roles appear in search results |
| **Filter fields** | Which profile fields can be used as search filters (comma-separated) |
| **Visibility for visitors** | What anonymous users can see |
| **Visibility for signed-in users** | What authenticated users can see |

Expand **Anonymous search access policy** to control whether unauthenticated users can search, and which filters they can use.

Expand **Advanced discovery AI options** for vector search, RAG, similarity thresholds, and retrieval modes.

### Profile fields

Each role has one or more sections, and each section has fields. Fields define what profile data users fill out.

![Compact field rows with collapsible sections](screenshots/placeholder-step6-fields.png)

Each field has:

- **Key** — internal identifier (e.g. `farm_name`).
- **Label** — what the user sees (e.g. "Farm Name").
- **Type** — text, number, select, multi_select, date, file, rich_text, or location.
- **Req** — whether the field is required for profile completeness.

Click the **Visibility, search, options** toggle on any field to set:

- **Visibility** — `public` (everyone), `protected` (signed-in only), or `private` (owner + admins).
- **Options** — comma-separated choices for select/multi_select fields.
- **Searchable** — whether this field is included in the search index.

> **Tip:** Start with 3–5 fields per role. You can add more later.

---

## Step 7 — Review, validate, and generate

The final step shows a risk check and gives you controls to save, validate, and generate.

![Review step with risk warnings and action buttons](screenshots/placeholder-step7-review.png)

### Risk warnings

The wizard flags common misconfigurations:

- All roles auto-approved (no quality gate)
- No communication rules (users can't contact each other)
- No searchable roles (discovery returns nothing)
- Incompatible AI mode settings

### Actions

| Button | What it does |
|--------|-------------|
| **Save Config** | Writes your configuration to `marketplace.yaml` |
| **Check Generated Sync** | Verifies if generated code matches your current config |
| **Generate Project** | Compiles your config into database migrations, API routes, and models |

### Typical flow

1. Review the risk warnings and go back to fix anything flagged.
2. Click **Save Config**.
3. Click **Generate Project**.
4. Check the generation report for any warnings.

After generation, close the wizard and start the full stack:

```bash
make setup-down
make up
make wait-api
make bootstrap-admin ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=YourPassword
```

---

## Using the glossary

Click **Open Glossary** (bottom-right button on any screen) to search every marketplace concept and configuration term.

![Glossary drawer with search](screenshots/placeholder-glossary.png)

Hover over any **?** button next to a field label to see:

- What the field controls
- Why it matters
- A concrete example
- The recommended default
- Risk level

---

## Using the advanced JSON editor

For power users: click **Advanced JSON** in the wizard header to open a side panel where you can edit the raw configuration JSON.

![JSON editor with diff preview](screenshots/placeholder-json-editor.png)

The editor provides:

- **Live syntax checking** — immediate feedback on JSON errors.
- **Schema validation** — checks your JSON against the backend schema.
- **Impact preview** — shows what will change if you apply, with destructive changes flagged in red.
- **Format JSON** — auto-formats for readability.
- **Apply to Guided Setup** — merges your JSON edits back into the wizard form.

> **Caution:** The editor warns you before applying changes that rename slugs or remove roles. These are breaking changes if you've already generated your project.

---

## After setup

Once you've generated your project, your marketplace is ready to run. See [Getting Started](getting-started.md) for the full boot sequence, or [Generation](generation.md) for details on what was generated.

| Next step | Guide |
|-----------|-------|
| Boot the API and worker | [Getting Started](getting-started.md) |
| Understand generated artifacts | [Generation](generation.md) |
| Manage users via admin API | [Admin Guide](admin-guide.md) |
| Re-generate after config changes | [Generation — Re-compilation](generation.md) |
