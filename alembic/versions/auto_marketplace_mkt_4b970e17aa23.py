"""Generated marketplace metadata migration.

Revision ID: mkt_4b970e17aa23
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "mkt_4b970e17aa23"
down_revision = "mkt_cd0965b20114"
branch_labels = None
depends_on = None

ROLES = [{'slug': 'producer', 'name': 'Producer', 'role_kind': 'supply'}, {'slug': 'buyer', 'name': 'Buyer', 'role_kind': 'demand'}]
ROLE_PERMISSIONS = [{'slug': 'producer', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}, {'slug': 'buyer', 'can_list': False, 'can_search': True, 'can_initiate_conversation': True, 'can_receive_conversation': True, 'can_share_private_assets': False, 'requires_onboarding': True, 'requires_approval': False, 'visible_in_search': False}]
ONBOARDING_RULES = [{'slug': 'producer', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}, {'slug': 'buyer', 'requires_approval': False, 'approval_type': 'auto', 'document_upload_required': False, 'ai_extraction_enabled': False, 'ai_profile_generation': False, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 100}]
COMMUNICATION_RULES = [{'initiator': 'buyer', 'receiver': 'producer', 'requires_approval': True}]
PROFILE_FIELD_DEFS = [{'slug': 'producer', 'section_name': 'Basic Information', 'field_name': 'farm_name', 'field_label': 'Farm Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'producer', 'section_name': 'Basic Information', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['Canada', 'USA', 'Brazil', 'Australia', 'Argentina'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'producer', 'section_name': 'Basic Information', 'field_name': 'region', 'field_label': 'Region/Province', 'field_type': 'text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'producer', 'section_name': 'Basic Information', 'field_name': 'primary_crops', 'field_label': 'Primary Crops', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['Wheat', 'Barley', 'Canola', 'Oats', 'Lentils', 'Peas', 'Flax'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'producer', 'section_name': 'Basic Information', 'field_name': 'description', 'field_label': 'Description', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 5}, {'slug': 'producer', 'section_name': 'Production Details', 'field_name': 'annual_production', 'field_label': 'Annual Production (MT)', 'field_type': 'number', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 6}, {'slug': 'producer', 'section_name': 'Production Details', 'field_name': 'certifications', 'field_label': 'Certifications', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['Organic', 'Non-GMO', 'Fair Trade', 'ISO 22000'], 'accepted_types_json': None, 'ordinal': 7}, {'slug': 'producer', 'section_name': 'Production Details', 'field_name': 'protein_content', 'field_label': 'Protein Content Range (%)', 'field_type': 'text', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 8}, {'slug': 'producer', 'section_name': 'Production Details', 'field_name': 'storage_capacity', 'field_label': 'Storage Capacity (MT)', 'field_type': 'number', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 9}, {'slug': 'producer', 'section_name': 'Internal', 'field_name': 'financial_notes', 'field_label': 'Financial Notes', 'field_type': 'text', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 10}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'org_name', 'field_label': 'Organization Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['Canada', 'USA', 'Brazil', 'Japan', 'South Korea', 'Germany', 'Italy'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'business_type', 'field_label': 'Business Type', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['Mill', 'Brewery', 'Bakery', 'Trading Company', 'Food Manufacturer', 'Other'], 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'description', 'field_label': 'Description', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'buyer', 'section_name': 'Sourcing Needs', 'field_name': 'crops_of_interest', 'field_label': 'Crops of Interest', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': ['Wheat', 'Barley', 'Canola', 'Oats', 'Lentils', 'Peas', 'Flax'], 'accepted_types_json': None, 'ordinal': 5}, {'slug': 'buyer', 'section_name': 'Sourcing Needs', 'field_name': 'annual_volume_needed', 'field_label': 'Annual Volume Needed (MT)', 'field_type': 'number', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 6}]
SPEC_HASH = "4b970e17aa2350d689f9f26f8464b440084be857625a93469a8ba05af455914e"
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
    op.execute("DELETE FROM marketplace_builds WHERE spec_hash = '4b970e17aa2350d689f9f26f8464b440084be857625a93469a8ba05af455914e'")
    # Keep metadata tables in place to avoid destructive behavior for previous builds.
