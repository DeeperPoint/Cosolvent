"""Generated marketplace metadata migration.

Revision ID: mkt_8b6cf8bc4e34
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "mkt_8b6cf8bc4e34"
down_revision = "merge_heads_0002"
branch_labels = None
depends_on = None

ROLES = [{'slug': 'machine_shop', 'name': 'Machine Shop', 'role_kind': 'supply'}, {'slug': 'buyer', 'name': 'Buyer', 'role_kind': 'demand'}, {'slug': 'service_provider', 'name': 'Service Provider', 'role_kind': 'facilitator'}]
ROLE_PERMISSIONS = [{'slug': 'machine_shop', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}, {'slug': 'buyer', 'can_list': False, 'can_search': True, 'can_initiate_conversation': True, 'can_receive_conversation': True, 'can_share_private_assets': False, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': False}, {'slug': 'service_provider', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}]
ONBOARDING_RULES = [{'slug': 'machine_shop', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}, {'slug': 'buyer', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': False, 'ai_extraction_enabled': False, 'ai_profile_generation': False, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 70}, {'slug': 'service_provider', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}]
COMMUNICATION_RULES = [{'initiator': 'buyer', 'receiver': 'machine_shop', 'requires_approval': True}, {'initiator': 'buyer', 'receiver': 'service_provider', 'requires_approval': True}, {'initiator': 'machine_shop', 'receiver': 'service_provider', 'requires_approval': True}]
PROFILE_FIELD_DEFS = [{'slug': 'machine_shop', 'section_name': 'Company', 'field_name': 'legal_name', 'field_label': 'Company Name', 'field_type': 'text', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'machine_shop', 'section_name': 'Company', 'field_name': 'location_region', 'field_label': 'Region', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'machine_shop', 'section_name': 'Company', 'field_name': 'location_precise', 'field_label': 'City / Address', 'field_type': 'text', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'machine_shop', 'section_name': 'Company', 'field_name': 'headcount', 'field_label': 'Headcount', 'field_type': 'number', 'visibility': 'public', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'machine_shop', 'section_name': 'Company', 'field_name': 'founded_year', 'field_label': 'Founded', 'field_type': 'number', 'visibility': 'public', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 5}, {'slug': 'machine_shop', 'section_name': 'Company', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 6}, {'slug': 'machine_shop', 'section_name': 'Compliance', 'field_name': 'certifications', 'field_label': 'Certifications', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['ISO 9001:2015', 'AS9100D', 'AS9102', 'NADCAP', 'CGP registered'], 'accepted_types_json': None, 'ordinal': 7}, {'slug': 'machine_shop', 'section_name': 'Compliance', 'field_name': 'nadcap_subscope', 'field_label': 'NADCAP Subscopes', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['Measurement & Inspection', 'Heat Treating', 'Welding', 'NDT', 'Chemical Processing', 'Nonconventional Machining', 'Coatings'], 'accepted_types_json': None, 'ordinal': 8}, {'slug': 'machine_shop', 'section_name': 'Compliance', 'field_name': 'export_status', 'field_label': 'Controlled Goods (CGP)', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['CGP', 'EIPA', 'none'], 'accepted_types_json': None, 'ordinal': 9}, {'slug': 'machine_shop', 'section_name': 'Capabilities', 'field_name': 'processes', 'field_label': 'Processes', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['3-axis milling', '4-axis milling', '5-axis milling', 'turning', 'mill-turn', 'wire EDM', 'sinker EDM', 'surface grinding', 'cylindrical grinding'], 'accepted_types_json': None, 'ordinal': 10}, {'slug': 'machine_shop', 'section_name': 'Capabilities', 'field_name': 'machine_type', 'field_label': 'Machine Types', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['vertical_machining_center', 'horizontal_machining_center', 'mill_turn', 'cnc_lathe', 'wire_edm'], 'accepted_types_json': None, 'ordinal': 11}, {'slug': 'machine_shop', 'section_name': 'Capabilities', 'field_name': 'machine_make_model', 'field_label': 'Machines', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['Haas VF-3SSYT', 'Haas TM-1P', 'Haas Super Mini Mill 2', 'Mazak Integrex i200S', 'AGMA VMC158'], 'accepted_types_json': None, 'ordinal': 12}, {'slug': 'machine_shop', 'section_name': 'Capabilities', 'field_name': 'materials_handled', 'field_label': 'Materials', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['Inconel 718', 'Ti-6Al-4V', '17-4 PH SS', '15-5 PH SS', 'A286', 'Hastelloy X', '7075-T6 Al', '6061-T6 Al'], 'accepted_types_json': None, 'ordinal': 13}, {'slug': 'machine_shop', 'section_name': 'Capabilities', 'field_name': 'work_envelope_mm', 'field_label': 'Work Envelope (mm)', 'field_type': 'text', 'visibility': 'public', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 14}, {'slug': 'machine_shop', 'section_name': 'Capabilities', 'field_name': 'linear_tolerance', 'field_label': 'Linear Tolerance (in)', 'field_type': 'text', 'visibility': 'public', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 15}, {'slug': 'machine_shop', 'section_name': 'Capabilities', 'field_name': 'surface_finish_ra', 'field_label': 'Surface Finish (Ra µin)', 'field_type': 'text', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 16}, {'slug': 'machine_shop', 'section_name': 'Capabilities', 'field_name': 'inspection_equipment', 'field_label': 'Inspection Equipment', 'field_type': 'text', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 17}, {'slug': 'machine_shop', 'section_name': 'Capacity', 'field_name': 'capacity_utilization_pct', 'field_label': 'Current Utilization (%)', 'field_type': 'number', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 18}, {'slug': 'machine_shop', 'section_name': 'Capacity', 'field_name': 'pipeline_utilization_pct', 'field_label': 'Pipeline Utilization (%)', 'field_type': 'number', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 19}, {'slug': 'machine_shop', 'section_name': 'Capacity', 'field_name': 'available_windows', 'field_label': 'Available Windows', 'field_type': 'rich_text', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 20}, {'slug': 'machine_shop', 'section_name': 'Capacity', 'field_name': 'lead_time_days', 'field_label': 'Lead Time (days)', 'field_type': 'number', 'visibility': 'public', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 21}, {'slug': 'machine_shop', 'section_name': 'Internal', 'field_name': 'constraints', 'field_label': 'Constraints / Policy', 'field_type': 'text', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 22}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'legal_name', 'field_label': 'Organization Name', 'field_type': 'text', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'location_region', 'field_label': 'Region', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'location_precise', 'field_label': 'City / Address', 'field_type': 'text', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'certifications', 'field_label': 'Certifications', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['AS9100D', 'ISO 9001:2015', 'CGP registered'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 5}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'required_processes', 'field_label': 'Required Processes', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['3-axis milling', '4-axis milling', '5-axis milling', 'turning', 'mill-turn', 'wire EDM'], 'accepted_types_json': None, 'ordinal': 6}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'required_materials', 'field_label': 'Required Materials', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['Inconel 718', 'Ti-6Al-4V', '17-4 PH SS', 'A286', '7075-T6 Al'], 'accepted_types_json': None, 'ordinal': 7}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'part_envelope_mm', 'field_label': 'Part Envelope (mm)', 'field_type': 'text', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 8}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'tolerance_required', 'field_label': 'Tolerance Required (in)', 'field_type': 'text', 'visibility': 'protected', 'required': True, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 9}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'tolerance_preferred', 'field_label': 'Tolerance Preferred (in)', 'field_type': 'text', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 10}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'surface_finish_required', 'field_label': 'Surface Finish Required (Ra µin)', 'field_type': 'text', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 11}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'supplier_constraints', 'field_label': 'Supplier Constraints', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['Canada-based only', 'CGP registration required', 'AS9100D required', 'NADCAP required'], 'accepted_types_json': None, 'ordinal': 12}, {'slug': 'buyer', 'section_name': 'Program', 'field_name': 'program_quantity', 'field_label': 'Program Quantity', 'field_type': 'number', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 13}, {'slug': 'buyer', 'section_name': 'Program', 'field_name': 'needed_by', 'field_label': 'Needed By', 'field_type': 'text', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 14}, {'slug': 'buyer', 'section_name': 'Program', 'field_name': 'annual_volume_forecast', 'field_label': '12-mo Volume Forecast', 'field_type': 'number', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 15}, {'slug': 'service_provider', 'section_name': 'Company', 'field_name': 'legal_name', 'field_label': 'Company Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'service_provider', 'section_name': 'Company', 'field_name': 'location_region', 'field_label': 'Region', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'service_provider', 'section_name': 'Company', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'services_offered', 'field_label': 'Services Offered', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['Inspection (FAI / AS9102)', 'Logistics', 'Trade Finance', 'Insurance', 'Export / Customs Brokerage'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'service_regions', 'field_label': 'Service Regions', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['Hamilton', 'Kitchener-Waterloo', 'Cambridge', 'Mississauga', 'Greater Toronto Area', 'Ontario-wide', 'National'], 'accepted_types_json': None, 'ordinal': 5}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'accreditation', 'field_label': 'Accreditation', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['ISO/IEC 17025', 'NADCAP', 'AS9102'], 'accepted_types_json': None, 'ordinal': 6}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'inspection_scope', 'field_label': 'Inspection Scope', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['FAI per AS9102', 'CMM', 'laser scanning', 'source inspection'], 'accepted_types_json': None, 'ordinal': 7}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'fee_model', 'field_label': 'Fee Model', 'field_type': 'text', 'visibility': 'public', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': None, 'ordinal': 8}, {'slug': 'service_provider', 'section_name': 'Services', 'field_name': 'credentials', 'field_label': 'Credentials', 'field_type': 'files', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': ['pdf'], 'ordinal': 9}]
SPEC_HASH = "8b6cf8bc4e34c3995a6d4dcf7c8b775a6433df83d0b632b6e2bb81c7be15e0ef"
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
    op.execute("DELETE FROM marketplace_builds WHERE spec_hash = '8b6cf8bc4e34c3995a6d4dcf7c8b775a6433df83d0b632b6e2bb81c7be15e0ef'")
    # Keep metadata tables in place to avoid destructive behavior for previous builds.
