"""Generated marketplace metadata migration.

Revision ID: mkt_fdc097f304d2
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "mkt_fdc097f304d2"
# Reparented from the deleted snapshot "mkt_670a55764f43" onto the surviving
# marketplace tip so the migration graph is whole again (the missing revision
# was a regenerated snapshot that was removed, leaving this one dangling).
down_revision = "mkt_5ed8adda2d87"
branch_labels = None
depends_on = None

ROLES = [{'slug': 'seller', 'name': 'Seller', 'role_kind': 'supply'}, {'slug': 'buyer', 'name': 'Buyer', 'role_kind': 'demand'}, {'slug': 'service_provider', 'name': 'Service Provider', 'role_kind': 'facilitator'}]
ROLE_PERMISSIONS = [{'slug': 'seller', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}, {'slug': 'buyer', 'can_list': False, 'can_search': True, 'can_initiate_conversation': True, 'can_receive_conversation': True, 'can_share_private_assets': False, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': False}, {'slug': 'service_provider', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}]
ONBOARDING_RULES = [{'slug': 'seller', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}, {'slug': 'buyer', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': False, 'ai_extraction_enabled': False, 'ai_profile_generation': False, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 70}, {'slug': 'service_provider', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}]
COMMUNICATION_RULES = [{'initiator': 'buyer', 'receiver': 'seller', 'requires_approval': True}, {'initiator': 'buyer', 'receiver': 'service_provider', 'requires_approval': True}]
PROFILE_FIELD_DEFS = [{'slug': 'seller', 'section_name': 'Company', 'field_name': 'company_name', 'field_label': 'Company Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'seller', 'section_name': 'Company', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['united_states', 'canada', 'mexico', 'germany', 'italy', 'japan', 'china', 'south_korea', 'india', 'brazil'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'seller', 'section_name': 'Company', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'seller', 'section_name': 'Offering', 'field_name': 'category', 'field_label': 'Category', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['construction', 'agriculture', 'manufacturing_cnc', 'material_handling', 'mining', 'power_generation', 'forestry', 'oil_and_gas'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'seller', 'section_name': 'Offering', 'field_name': 'brand', 'field_label': 'Brand', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['caterpillar', 'komatsu', 'john_deere', 'volvo', 'hitachi', 'jcb', 'liebherr', 'doosan', 'mitsubishi'], 'accepted_types_json': None, 'ordinal': 5}, {'slug': 'seller', 'section_name': 'Offering', 'field_name': 'condition', 'field_label': 'Condition', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['new', 'used', 'refurbished', 'parts_only'], 'accepted_types_json': None, 'ordinal': 6}, {'slug': 'seller', 'section_name': 'Offering', 'field_name': 'operating_hours', 'field_label': 'Operating Hours', 'field_type': 'number', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 7}, {'slug': 'seller', 'section_name': 'Offering', 'field_name': 'emissions_standard', 'field_label': 'Emissions Standard', 'field_type': 'select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['epa_tier_2', 'epa_tier_3', 'epa_tier_4', 'eu_stage_v'], 'accepted_types_json': None, 'ordinal': 8}, {'slug': 'seller', 'section_name': 'Offering', 'field_name': 'spec_sheets', 'field_label': 'Spec Sheets / Documents', 'field_type': 'files', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': ['pdf'], 'ordinal': 9}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'company_name', 'field_label': 'Organization Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['united_states', 'canada', 'mexico', 'germany', 'italy', 'japan', 'china', 'south_korea', 'india', 'brazil'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'category', 'field_label': 'Category', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['construction', 'agriculture', 'manufacturing_cnc', 'material_handling', 'mining', 'power_generation', 'forestry', 'oil_and_gas'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'brand', 'field_label': 'Brand', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['caterpillar', 'komatsu', 'john_deere', 'volvo', 'hitachi', 'jcb', 'liebherr', 'doosan', 'mitsubishi'], 'accepted_types_json': None, 'ordinal': 5}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'condition', 'field_label': 'Condition', 'field_type': 'select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['new', 'used', 'refurbished', 'parts_only'], 'accepted_types_json': None, 'ordinal': 6}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'operating_hours', 'field_label': 'Operating Hours', 'field_type': 'number', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 7}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'emissions_standard', 'field_label': 'Emissions Standard', 'field_type': 'select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['epa_tier_2', 'epa_tier_3', 'epa_tier_4', 'eu_stage_v'], 'accepted_types_json': None, 'ordinal': 8}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'budget_range', 'field_label': 'Typical Budget per Order', 'field_type': 'select', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': ['Under 25k', '25k-100k', '100k-500k', '500k-2M', '2M+'], 'accepted_types_json': None, 'ordinal': 9}, {'slug': 'service_provider', 'section_name': 'Company', 'field_name': 'company_name', 'field_label': 'Company Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'service_provider', 'section_name': 'Company', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['united_states', 'canada', 'mexico', 'germany', 'italy', 'japan', 'china', 'south_korea', 'india', 'brazil'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'service_provider', 'section_name': 'Company', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'services_offered', 'field_label': 'Services Offered', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['Transport Carrier', 'Rigging Heavy Lift Specialist', 'Machinery Inspector', 'Customs Broker', 'Cargo Insurer'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'service_regions', 'field_label': 'Service Regions', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['North America', 'South America', 'Europe', 'Middle East', 'Africa', 'South Asia', 'East Asia', 'Southeast Asia', 'Oceania'], 'accepted_types_json': None, 'ordinal': 5}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'equipment_type', 'field_label': 'Equipment Type', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['flatbed', 'step_deck', 'double_drop_lowboy', 'removable_gooseneck_rgn', 'container', 'roll_on_roll_off', 'heavy_haul_specialized'], 'accepted_types_json': None, 'ordinal': 6}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'service_region', 'field_label': 'Service Region', 'field_type': 'select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['north_america', 'south_america', 'europe', 'middle_east', 'africa', 'south_asia', 'east_asia', 'southeast_asia', 'oceania'], 'accepted_types_json': None, 'ordinal': 7}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'carrier_credentials', 'field_label': 'Carrier Credentials', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['dot_compliant', 'adr', 'tir_carnet', 'iso_9001', 'c_tpat'], 'accepted_types_json': None, 'ordinal': 8}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'cargo_insurance_usd', 'field_label': 'Cargo Insurance (USD)', 'field_type': 'number', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 9}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'credentials', 'field_label': 'Credentials / Certificates', 'field_type': 'files', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': ['pdf'], 'ordinal': 10}]
SPEC_HASH = "fdc097f304d2695d7c174d3dd7c927389b33742b41e2839f48aa5d85d3abd03a"
BUILD_MODE = "mvp"
GENERATOR_VERSION = "1.0.0"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("""
    CREATE TABLE IF NOT EXISTS marketplace_roles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        slug TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        role_kind TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS marketplace_role_permissions (
        role_id UUID PRIMARY KEY REFERENCES marketplace_roles(id) ON DELETE CASCADE,
        can_list BOOLEAN NOT NULL DEFAULT FALSE,
        can_search BOOLEAN NOT NULL DEFAULT FALSE,
        can_initiate_conversation BOOLEAN NOT NULL DEFAULT FALSE,
        can_receive_conversation BOOLEAN NOT NULL DEFAULT FALSE,
        can_share_private_assets BOOLEAN NOT NULL DEFAULT FALSE,
        requires_onboarding BOOLEAN NOT NULL DEFAULT TRUE,
        requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
        visible_in_search BOOLEAN NOT NULL DEFAULT FALSE,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS marketplace_onboarding_rules (
        role_id UUID PRIMARY KEY REFERENCES marketplace_roles(id) ON DELETE CASCADE,
        requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
        approval_type TEXT NOT NULL DEFAULT 'manual',
        document_upload_required BOOLEAN NOT NULL DEFAULT FALSE,
        ai_extraction_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        ai_profile_generation BOOLEAN NOT NULL DEFAULT FALSE,
        welcome_email_on_approval BOOLEAN NOT NULL DEFAULT TRUE,
        profile_completeness_threshold INTEGER NOT NULL DEFAULT 100,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS marketplace_communication_rules (
        initiator_role_id UUID NOT NULL REFERENCES marketplace_roles(id) ON DELETE CASCADE,
        receiver_role_id UUID NOT NULL REFERENCES marketplace_roles(id) ON DELETE CASCADE,
        requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (initiator_role_id, receiver_role_id)
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS marketplace_profile_field_defs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        role_id UUID NOT NULL REFERENCES marketplace_roles(id) ON DELETE CASCADE,
        section_name TEXT NOT NULL,
        field_name TEXT NOT NULL,
        field_label TEXT NOT NULL,
        field_type TEXT NOT NULL,
        visibility TEXT NOT NULL DEFAULT 'public',
        required BOOLEAN NOT NULL DEFAULT FALSE,
        searchable BOOLEAN NOT NULL DEFAULT FALSE,
        options_json JSONB NULL,
        accepted_types_json JSONB NULL,
        ordinal INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (role_id, section_name, field_name)
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS marketplace_builds (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        spec_hash TEXT NOT NULL UNIQUE,
        mode TEXT NOT NULL,
        generator_version TEXT NOT NULL,
        generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketplace_roles_slug ON marketplace_roles (slug)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_marketplace_profile_field_defs_lookup "
        "ON marketplace_profile_field_defs (role_id, section_name, ordinal)"
    )

    conn = op.get_bind()

    for row in ROLES:
        conn.execute(
            sa.text(
                """
                INSERT INTO marketplace_roles (slug, name, role_kind, is_active, updated_at)
                VALUES (:slug, :name, :role_kind, TRUE, NOW())
                ON CONFLICT (slug) DO UPDATE
                SET name = EXCLUDED.name,
                    role_kind = EXCLUDED.role_kind,
                    is_active = TRUE,
                    updated_at = NOW()
                """
            ),
            row,
        )

    for row in ROLE_PERMISSIONS:
        conn.execute(
            sa.text(
                """
                INSERT INTO marketplace_role_permissions (
                    role_id,
                    can_list,
                    can_search,
                    can_initiate_conversation,
                    can_receive_conversation,
                    can_share_private_assets,
                    requires_onboarding,
                    requires_approval,
                    visible_in_search,
                    updated_at
                )
                SELECT
                    r.id,
                    :can_list,
                    :can_search,
                    :can_initiate_conversation,
                    :can_receive_conversation,
                    :can_share_private_assets,
                    :requires_onboarding,
                    :requires_approval,
                    :visible_in_search,
                    NOW()
                FROM marketplace_roles r
                WHERE r.slug = :slug
                ON CONFLICT (role_id) DO UPDATE
                SET can_list = EXCLUDED.can_list,
                    can_search = EXCLUDED.can_search,
                    can_initiate_conversation = EXCLUDED.can_initiate_conversation,
                    can_receive_conversation = EXCLUDED.can_receive_conversation,
                    can_share_private_assets = EXCLUDED.can_share_private_assets,
                    requires_onboarding = EXCLUDED.requires_onboarding,
                    requires_approval = EXCLUDED.requires_approval,
                    visible_in_search = EXCLUDED.visible_in_search,
                    updated_at = NOW()
                """
            ),
            row,
        )

    for row in ONBOARDING_RULES:
        conn.execute(
            sa.text(
                """
                INSERT INTO marketplace_onboarding_rules (
                    role_id,
                    requires_approval,
                    approval_type,
                    document_upload_required,
                    ai_extraction_enabled,
                    ai_profile_generation,
                    welcome_email_on_approval,
                    profile_completeness_threshold,
                    updated_at
                )
                SELECT
                    r.id,
                    :requires_approval,
                    :approval_type,
                    :document_upload_required,
                    :ai_extraction_enabled,
                    :ai_profile_generation,
                    :welcome_email_on_approval,
                    :profile_completeness_threshold,
                    NOW()
                FROM marketplace_roles r
                WHERE r.slug = :slug
                ON CONFLICT (role_id) DO UPDATE
                SET requires_approval = EXCLUDED.requires_approval,
                    approval_type = EXCLUDED.approval_type,
                    document_upload_required = EXCLUDED.document_upload_required,
                    ai_extraction_enabled = EXCLUDED.ai_extraction_enabled,
                    ai_profile_generation = EXCLUDED.ai_profile_generation,
                    welcome_email_on_approval = EXCLUDED.welcome_email_on_approval,
                    profile_completeness_threshold = EXCLUDED.profile_completeness_threshold,
                    updated_at = NOW()
                """
            ),
            row,
        )

    for row in COMMUNICATION_RULES:
        conn.execute(
            sa.text(
                """
                INSERT INTO marketplace_communication_rules (
                    initiator_role_id, receiver_role_id, requires_approval, updated_at
                )
                SELECT i.id, r.id, :requires_approval, NOW()
                FROM marketplace_roles i
                JOIN marketplace_roles r ON r.slug = :receiver
                WHERE i.slug = :initiator
                ON CONFLICT (initiator_role_id, receiver_role_id) DO UPDATE
                SET requires_approval = EXCLUDED.requires_approval,
                    updated_at = NOW()
                """
            ),
            row,
        )

    conn.execute(sa.text("DELETE FROM marketplace_profile_field_defs"))
    for row in PROFILE_FIELD_DEFS:
        payload = dict(row)
        payload["options_json"] = json.dumps(payload["options_json"]) if payload.get("options_json") is not None else None
        payload["accepted_types_json"] = json.dumps(payload["accepted_types_json"]) if payload.get("accepted_types_json") is not None else None
        conn.execute(
            sa.text(
                """
                INSERT INTO marketplace_profile_field_defs (
                    role_id,
                    section_name,
                    field_name,
                    field_label,
                    field_type,
                    visibility,
                    required,
                    searchable,
                    options_json,
                    accepted_types_json,
                    ordinal,
                    updated_at
                )
                SELECT
                    r.id,
                    :section_name,
                    :field_name,
                    :field_label,
                    :field_type,
                    :visibility,
                    :required,
                    :searchable,
                    CAST(:options_json AS JSONB),
                    CAST(:accepted_types_json AS JSONB),
                    :ordinal,
                    NOW()
                FROM marketplace_roles r
                WHERE r.slug = :slug
                """
            ),
            payload,
        )

    conn.execute(
        sa.text(
            """
            INSERT INTO marketplace_builds (spec_hash, mode, generator_version, generated_at)
            VALUES (:spec_hash, :mode, :generator_version, NOW())
            ON CONFLICT (spec_hash) DO UPDATE
            SET mode = EXCLUDED.mode,
                generator_version = EXCLUDED.generator_version,
                generated_at = NOW()
            """
        ),
        {
            "spec_hash": SPEC_HASH,
            "mode": BUILD_MODE,
            "generator_version": GENERATOR_VERSION,
        },
    )


def downgrade() -> None:
    op.execute("DELETE FROM marketplace_builds WHERE spec_hash = 'fdc097f304d2695d7c174d3dd7c927389b33742b41e2839f48aa5d85d3abd03a'")
    # Keep metadata tables in place to avoid destructive behavior for previous builds.
