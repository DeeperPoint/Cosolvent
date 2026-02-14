# CLI Wizard

The CLI wizard generates a `marketplace.yaml` configuration file through an interactive 7-step process.

## Usage

```bash
# Run the interactive wizard
python -m cli wizard

# Specify output file
python -m cli wizard -o my-marketplace.yaml

# Start from a preset (skips steps 1-6)
python -m cli wizard --preset agriculture
python -m cli wizard --preset professional_services

# Validate an existing config file
python -m cli validate marketplace.yaml
python -m cli validate /path/to/config.yaml
```

When no subcommand is given, `python -m cli` defaults to running the wizard.

## Wizard Steps

### Step 1: Marketplace Identity

Prompts for:
- **Name** — marketplace display name
- **Description** — short description
- **Industry** — industry vertical

### Step 2: Participant Types

Define 2–3 participant types. For each:
- **Name** — display name (e.g., "Producer")
- **Slug** — URL-safe identifier (e.g., "producer")
- **Role** — `supply`, `demand`, or `facilitator`
- **Permissions** — 8 boolean flags controlling what the type can do

### Step 3: Profile Schemas

For each participant type, define profile sections and fields:
- **Sections** — named groups of fields (e.g., "Basic Information")
- **Fields** — individual data points with type, label, required flag, visibility level, and searchability

Supported field types: `text`, `number`, `select`, `multi_select`, `date`, `file`, `rich_text`, `location`.

### Step 4: Onboarding Workflows

For each participant type:
- Whether admin approval is required
- Approval type (manual or auto)
- Document upload requirements
- AI feature flags (extraction, profile generation)
- Welcome email and completeness threshold

### Step 5: Communication Rules

Define which types can initiate conversations with which other types, and whether approval is required for each pair.

### Step 6: Discovery Configuration

- Which types are searchable
- Which fields are available as filters
- Result visibility tiers (anonymous vs authenticated)
- AI feature toggles (vector search, RAG, follow-ups)

### Step 7: Review & Generate

Displays a YAML summary of the entire configuration. The user confirms or cancels. On confirmation, the config is validated against the `MarketplaceConfig` Pydantic schema before writing the file.

## Presets

Presets provide complete, pre-built configurations that can be used as starting points.

### Agriculture (`agriculture`)

- **Marketplace:** GrainPlaza — specialty grain marketplace
- **Types:** Producer (supply) + Buyer (demand)
- **Features:** Document upload for producers, AI extraction, manual approval
- **Profiles:** Farm name, country, primary crops (producer); org name (buyer)

### Professional Services (`professional_services`)

- **Marketplace:** ProConnect — professional service marketplace
- **Types:** Provider (supply) + Client (demand)
- **Features:** AI profile generation for providers, manual approval
- **Profiles:** Company name, services, industry focus, description, team size (provider); org name, industry (client)

## Validation Command

The `validate` subcommand checks a YAML file against the full `MarketplaceConfig` schema without starting the server:

```bash
$ python -m cli validate marketplace.yaml
Valid! Marketplace: GrainPlaza
  Industry: Specialty Agriculture
  Participant types: producer, buyer
```

On validation failure, it reports per-field errors:

```bash
$ python -m cli validate bad-config.yaml
Validation errors:

  participant_types: At least 2 participant types required
  discovery -> filter_fields -> 0: Discovery filter_field 'nonexistent' not found in any profile schema
```

Exit codes: `0` on success, `1` on failure.
