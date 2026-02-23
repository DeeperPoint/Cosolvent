# Setup Wizard

The setup wizard is a 7-step browser UI for configuring your marketplace. It guides you from a blank slate to a validated, generated `marketplace.yaml` without writing YAML by hand.

## Opening the Wizard

Start the setup service:

```bash
make setup-up
```

Then open:

```
http://localhost:18080/onboarding
```

Click **Start setup** on the intro screen to enter the wizard.

> **Tip:** Click **Open Glossary** in the bottom-right corner at any time to search every marketplace concept. Hover over any **?** button next to a field to see what it does, why it matters, and the recommended default.

---

## Step 1 — Choose a Starting Template

Pick the template closest to your marketplace. Templates pre-fill every subsequent step with sensible defaults.

| Template | Supply-side | Demand-side | Best for |
|----------|------------|-------------|----------|
| Agriculture | Producer | Buyer | Crop exchanges, farm-to-buyer |
| B2B Services | Service Provider | Client | Professional services matching |
| Manufacturing | Manufacturer | Buyer | Parts, materials sourcing |

Two quick dropdowns tune the template:
- **Team readiness** — `Lean` lowers approval thresholds; `Compliance-heavy` raises them
- **Launch style** — `Fast MVP` auto-approves demand-side roles; `Curated` adds document requirements for supply-side roles

You can fine-tune all defaults in the steps that follow.

---

## Step 2 — Marketplace Basics

Set your marketplace's identity. These appear in exports, admin panels, and generated documentation.

| Field | Example | Notes |
|-------|---------|-------|
| **Name** | AgriExchange | Your brand name |
| **Industry** | Specialty Agriculture | The vertical you operate in |
| **Description** | Connects producers with wholesale buyers | One sentence about what your marketplace does |

---

## Step 3 — Roles and Capabilities

Define who participates. Every marketplace requires at least two participant types (supply-side and demand-side). A third facilitator type is optional.

For each role:

**Identity fields:**
| Field | What it means |
|-------|---------------|
| **Name** | Display name shown to users (e.g. "Producer") |
| **Slug** | Short internal identifier (e.g. `producer`). URL-safe, lowercase. Avoid changing after generation. |
| **Role type** | `supply`, `demand`, or `facilitator` |

**Permission flags:**

| Permission | What it controls |
|-----------|------------------|
| Can publish listings | Role can create public-facing profiles/listings |
| Can search profiles | Role can run discovery searches |
| Can start conversations | Role can initiate contact with others |
| Can receive conversations | Role can be contacted by others |
| Can share private files | Role can attach documents in conversations |
| Must complete onboarding | Role must finish profile before accessing the platform |
| Needs approval before active | Admin must approve the profile |
| Visible in search | Profile shows up in search results |

> **Tip:** Keep 2–3 roles for MVP. More roles multiply permission combinations and communication rules.

> **Warning:** Changing a slug after generating the project requires recompilation and a database migration. Avoid slug changes once the project is live.

---

## Step 4 — Onboarding and Approval

Set the trust and verification standards for each role.

| Setting | What it does |
|---------|-------------|
| **Require admin approval** | New profiles need manual review before going live |
| **Approval style** | `Manual review` — human reviews each; `Auto approve` — instant activation |
| **Minimum completeness** | Profile must be N% filled before submitting (0–100) |

**Advanced onboarding options:**

| Setting | What it does |
|---------|-------------|
| **Require documents on onboarding** | Users must upload files (certifications, licenses) |
| **Enable AI extraction from documents** | System reads uploaded docs and pre-fills profile fields |
| **Enable AI profile drafts** | System generates a draft profile from uploaded content |
| **Send welcome email when approved** | Automatic notification on approval |

> **Recommendation:** Require approval for supply-side roles (they are the scarce, high-trust side). Auto-approve demand-side roles for faster activation and lower friction.

---

## Step 5 — Communication Rules

Define who can contact whom. Without rules, users cannot send messages.

Each rule specifies:
- **Initiator** — the role that starts the conversation
- **Receiver** — the role that receives the request
- **Requires approval** — the receiver must accept before the conversation begins

Click **Add Communication Rule** to create additional rules.

> **Example:** Buyer initiates contact with Producer; Producer must accept the request. This gives supply-side control over who they engage with.

---

## Step 6 — Profile Fields and Discovery

This step has two sections: **Discovery** settings and **Profile schema** (fields per role).

### Discovery

| Setting | What it controls |
|---------|-----------------|
| **Searchable roles** | Which roles appear in search results |
| **Filter fields** | Which profile fields can be used as search filters |
| **Visibility for anonymous users** | What unauthenticated visitors can see |
| **Visibility for signed-in users** | What authenticated users can see |

**Anonymous search access policy:** Controls whether unauthenticated users can search and which filters they can use. Disabled by default — recommended to keep disabled unless you intentionally want public search.

**Advanced discovery AI options:** Vector search, RAG, similarity thresholds, and retrieval modes. See [AI Features](ai-features.md) for details.

### Profile Fields

Each role has one or more sections, and each section has fields. Fields define what profile data users fill out.

**Core field properties:**

| Property | What it does |
|----------|-------------|
| **Key** | Internal identifier (e.g. `farm_name`). Must be unique within the role. |
| **Label** | What the user sees (e.g. "Farm Name") |
| **Type** | `text`, `number`, `select`, `multi_select`, `date`, `file`, `rich_text`, or `location` |
| **Req** | Whether the field counts toward profile completeness |

**Per-field advanced options (expand the row):**

| Property | What it does |
|----------|-------------|
| **Visibility** | `public` (everyone), `protected` (signed-in only), `private` (owner + admins only) |
| **Options** | Comma-separated choices for `select`/`multi_select` fields |
| **Searchable** | Whether this field is included in the search index |

**Visibility guide:**

| Level | Seen by | Use for |
|-------|---------|---------|
| `public` | Everyone, including anonymous | Name, company, category |
| `protected` | Authenticated users only | Capacity, pricing range |
| `private` | Profile owner + admins only | Notes, financial data |

> **Tip:** Start with 3–5 fields per role. You can add more fields at any time by re-running the wizard.

---

## Step 7 — Review, Validate, and Generate

The final step checks your configuration and gives you controls to save and generate.

### Risk Warnings

The wizard flags common misconfigurations:
- All roles auto-approved (no quality gate)
- No communication rules (users cannot contact each other)
- No searchable roles (discovery returns nothing)
- Incompatible AI mode settings (e.g. `rag_strict` with vector search disabled)

Review and go back to fix anything flagged.

### Actions

| Button | What it does |
|--------|-------------|
| **Save Config** | Writes your configuration to `marketplace.yaml` |
| **Check Generated Sync** | Verifies if generated artifacts match your current config |
| **Generate Project** | Compiles config into database migrations, API routes, and models |

### Typical Flow

1. Review risk warnings and fix anything flagged
2. Click **Save Config**
3. Click **Generate Project**
4. Review the generation report for warnings
5. Close the wizard and start the full stack

After generation:

```bash
make setup-down
make up
make wait-api
make bootstrap-admin ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=YourPassword
```

---

## Advanced JSON Editor

For power users: click **Advanced JSON** in the wizard header to open a side panel with direct config editing.

Features:
- **Live syntax checking** — immediate feedback on JSON errors
- **Schema validation** — validates against the backend schema on every keystroke (debounced)
- **Impact preview** — shows what will change with destructive changes flagged in red
- **Format JSON** — auto-formats for readability
- **Apply to Guided Setup** — merges JSON edits back into the wizard form

> **Warning:** The editor flags slug renames and role removals as destructive. If you have already generated artifacts, rename slugs only with intention — it requires recompilation and a migration.

---

## CLI Wizard (Alternative)

If you prefer the terminal over the browser:

```bash
# Interactive wizard
python -m cli wizard -o marketplace.yaml

# Start from a preset
python -m cli wizard --preset agriculture -o marketplace.yaml
python -m cli wizard --preset professional_services -o marketplace.yaml
```

The CLI wizard covers the same 7 steps in your terminal.

---

## See Also
- [Quick Start](quick-start.md) — full boot sequence
- [Marketplace Config Reference](marketplace-config.md) — every YAML field in detail
- [AI Features](ai-features.md) — AI provider setup and RAG configuration
- [Running](running.md) — starting and stopping the stack
