"""Generated marketplace metadata migration.

Revision ID: mkt_dbf5161a9d7a
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "mkt_dbf5161a9d7a"
down_revision = "mkt_9a6330f63fe9"
branch_labels = None
depends_on = None

ROLES = [{'slug': 'machine_shop', 'name': 'Machine Shop', 'role_kind': 'supply'}, {'slug': 'buyer', 'name': 'Buyer', 'role_kind': 'demand'}, {'slug': 'quality_inspector', 'name': 'Quality Inspector', 'role_kind': 'facilitator'}, {'slug': 'rigging_logistics_provider', 'name': 'Rigging Logistics Provider', 'role_kind': 'facilitator'}, {'slug': 'cargo_insurer', 'name': 'Cargo Insurer', 'role_kind': 'facilitator'}, {'slug': 'trade_finance_provider', 'name': 'Trade Finance Provider', 'role_kind': 'facilitator'}, {'slug': 'certification_body', 'name': 'Certification Body', 'role_kind': 'facilitator'}]
ROLE_PERMISSIONS = [{'slug': 'machine_shop', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}, {'slug': 'buyer', 'can_list': False, 'can_search': True, 'can_initiate_conversation': True, 'can_receive_conversation': True, 'can_share_private_assets': False, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': False}, {'slug': 'quality_inspector', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}, {'slug': 'rigging_logistics_provider', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}, {'slug': 'cargo_insurer', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}, {'slug': 'trade_finance_provider', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}, {'slug': 'certification_body', 'can_list': True, 'can_search': False, 'can_initiate_conversation': False, 'can_receive_conversation': True, 'can_share_private_assets': True, 'requires_onboarding': True, 'requires_approval': True, 'visible_in_search': True}]
ONBOARDING_RULES = [{'slug': 'machine_shop', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}, {'slug': 'buyer', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': False, 'ai_extraction_enabled': False, 'ai_profile_generation': False, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 70}, {'slug': 'quality_inspector', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}, {'slug': 'rigging_logistics_provider', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}, {'slug': 'cargo_insurer', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}, {'slug': 'trade_finance_provider', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}, {'slug': 'certification_body', 'requires_approval': True, 'approval_type': 'manual', 'document_upload_required': True, 'ai_extraction_enabled': True, 'ai_profile_generation': True, 'welcome_email_on_approval': True, 'profile_completeness_threshold': 80}]
COMMUNICATION_RULES = [{'initiator': 'buyer', 'receiver': 'machine_shop', 'requires_approval': True}, {'initiator': 'buyer', 'receiver': 'quality_inspector', 'requires_approval': True}, {'initiator': 'buyer', 'receiver': 'rigging_logistics_provider', 'requires_approval': True}, {'initiator': 'buyer', 'receiver': 'cargo_insurer', 'requires_approval': True}, {'initiator': 'buyer', 'receiver': 'trade_finance_provider', 'requires_approval': True}, {'initiator': 'buyer', 'receiver': 'certification_body', 'requires_approval': True}]
PROFILE_FIELD_DEFS = [{'slug': 'machine_shop', 'section_name': 'Company', 'field_name': 'company_name', 'field_label': 'Company Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'machine_shop', 'section_name': 'Company', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['usa', 'canada', 'mexico', 'germany', 'brazil', 'india', 'china', 'japan'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'machine_shop', 'section_name': 'Company', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'machine_type', 'field_label': 'Machine Type', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['vertical_machining_center', 'cnc_lathe', '3_axis_mill', '4_axis_mill', '5_axis_machining_center', 'multiaxis_machining_center', 'laser_cutting', 'waterjet_cutting'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'tool_taper', 'field_label': 'Tool Taper', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['ct40', 'bt40', 'big_plus_no_40', 'big_plus_no_50'], 'accepted_types_json': None, 'ordinal': 5}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'max_spindle_speed_rpm', 'field_label': 'Max Spindle Speed (RPM)', 'field_type': 'number', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 6}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'table_load_limit_kg', 'field_label': 'Table Load Limit (kg)', 'field_type': 'number', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 7}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'deal_instrument', 'field_label': 'Deal Instrument', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['spot_purchase', 'capacity_rental', 'ongoing_subcontract'], 'accepted_types_json': None, 'ordinal': 8}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'material_grade', 'field_label': 'Material Grade', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['aluminum_7075_t6', 'aluminum_6061', 'ti_6al_4v', 'inconel_625', 'inconel_718', 'stainless_steel', 'carbon_steel', 'plastic'], 'accepted_types_json': None, 'ordinal': 9}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'material_family', 'field_label': 'Material Family', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['aluminum_alloy', 'titanium_alloy', 'nickel_superalloy', 'steel', 'non_ferrous', 'polymer'], 'accepted_types_json': None, 'ordinal': 10}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'required_processes', 'field_label': 'Required Processes', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['heat_treatment', 'coating', 'edm', 'threadmilling', 'inspection_cmm', 'deburring'], 'accepted_types_json': None, 'ordinal': 11}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'end_use_sector', 'field_label': 'End Use Sector', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['aerospace', 'defense', 'automotive', 'medical', 'power_generation', 'marine', 'general_industrial'], 'accepted_types_json': None, 'ordinal': 12}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'quality_certification', 'field_label': 'Quality Certification', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['iso_9001', 'as9100d', 'as9110', 'as9120', 'none'], 'accepted_types_json': None, 'ordinal': 13}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'tolerance_class', 'field_label': 'Tolerance Class', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['general', 'tight_precision', 'first_article_inspection', 'statistical_sampling'], 'accepted_types_json': None, 'ordinal': 14}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'inspection_method', 'field_label': 'Inspection Method', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['cmm_report', 'first_article_inspection', 'statistical_sampling_plan', 'visual'], 'accepted_types_json': None, 'ordinal': 15}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'rate_structure', 'field_label': 'Rate Structure', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['per_part', 'per_machine_hour', 'fixed_price'], 'accepted_types_json': None, 'ordinal': 16}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'payment_terms', 'field_label': 'Payment Terms', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['net_30', 'net_45', 'net_60', 'on_delivery'], 'accepted_types_json': None, 'ordinal': 17}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'currency', 'field_label': 'Currency', 'field_type': 'select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['cad', 'usd'], 'accepted_types_json': None, 'ordinal': 18}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'contract_stage', 'field_label': 'Contract Stage', 'field_type': 'select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['anonymous', 'mutual_nda', 'deal_context', 'subcontract_agreement'], 'accepted_types_json': None, 'ordinal': 19}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'economic_region', 'field_label': 'Economic Region', 'field_type': 'multi_select', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': ['toronto', 'kitchener_waterloo_barrie', 'windsor_sarnia', 'hamilton_niagara', 'london', 'ottawa', 'stratford_bruce'], 'accepted_types_json': None, 'ordinal': 20}, {'slug': 'machine_shop', 'section_name': 'Offering', 'field_name': 'spec_sheets', 'field_label': 'Spec Sheets / Documents', 'field_type': 'files', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': ['pdf'], 'ordinal': 21}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'company_name', 'field_label': 'Organization Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['usa', 'canada', 'mexico', 'germany', 'brazil', 'india', 'china', 'japan'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'buyer', 'section_name': 'Organization', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'machine_type', 'field_label': 'Machine Type', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['vertical_machining_center', 'cnc_lathe', '3_axis_mill', '4_axis_mill', '5_axis_machining_center', 'multiaxis_machining_center', 'laser_cutting', 'waterjet_cutting'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'tool_taper', 'field_label': 'Tool Taper', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['ct40', 'bt40', 'big_plus_no_40', 'big_plus_no_50'], 'accepted_types_json': None, 'ordinal': 5}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'max_spindle_speed_rpm', 'field_label': 'Max Spindle Speed (RPM)', 'field_type': 'number', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 6}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'table_load_limit_kg', 'field_label': 'Table Load Limit (kg)', 'field_type': 'number', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 7}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'deal_instrument', 'field_label': 'Deal Instrument', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['spot_purchase', 'capacity_rental', 'ongoing_subcontract'], 'accepted_types_json': None, 'ordinal': 8}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'material_grade', 'field_label': 'Material Grade', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['aluminum_7075_t6', 'aluminum_6061', 'ti_6al_4v', 'inconel_625', 'inconel_718', 'stainless_steel', 'carbon_steel', 'plastic'], 'accepted_types_json': None, 'ordinal': 9}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'material_family', 'field_label': 'Material Family', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['aluminum_alloy', 'titanium_alloy', 'nickel_superalloy', 'steel', 'non_ferrous', 'polymer'], 'accepted_types_json': None, 'ordinal': 10}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'required_processes', 'field_label': 'Required Processes', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['heat_treatment', 'coating', 'edm', 'threadmilling', 'inspection_cmm', 'deburring'], 'accepted_types_json': None, 'ordinal': 11}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'end_use_sector', 'field_label': 'End Use Sector', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['aerospace', 'defense', 'automotive', 'medical', 'power_generation', 'marine', 'general_industrial'], 'accepted_types_json': None, 'ordinal': 12}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'quality_certification', 'field_label': 'Quality Certification', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['iso_9001', 'as9100d', 'as9110', 'as9120', 'none'], 'accepted_types_json': None, 'ordinal': 13}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'tolerance_class', 'field_label': 'Tolerance Class', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['general', 'tight_precision', 'first_article_inspection', 'statistical_sampling'], 'accepted_types_json': None, 'ordinal': 14}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'inspection_method', 'field_label': 'Inspection Method', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['cmm_report', 'first_article_inspection', 'statistical_sampling_plan', 'visual'], 'accepted_types_json': None, 'ordinal': 15}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'rate_structure', 'field_label': 'Rate Structure', 'field_type': 'multi_select', 'visibility': 'protected', 'required': True, 'searchable': True, 'options_json': ['per_part', 'per_machine_hour', 'fixed_price'], 'accepted_types_json': None, 'ordinal': 16}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'payment_terms', 'field_label': 'Payment Terms', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['net_30', 'net_45', 'net_60', 'on_delivery'], 'accepted_types_json': None, 'ordinal': 17}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'currency', 'field_label': 'Currency', 'field_type': 'select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['cad', 'usd'], 'accepted_types_json': None, 'ordinal': 18}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'contract_stage', 'field_label': 'Contract Stage', 'field_type': 'select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['anonymous', 'mutual_nda', 'deal_context', 'subcontract_agreement'], 'accepted_types_json': None, 'ordinal': 19}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'economic_region', 'field_label': 'Economic Region', 'field_type': 'multi_select', 'visibility': 'protected', 'required': False, 'searchable': True, 'options_json': ['toronto', 'kitchener_waterloo_barrie', 'windsor_sarnia', 'hamilton_niagara', 'london', 'ottawa', 'stratford_bruce'], 'accepted_types_json': None, 'ordinal': 20}, {'slug': 'buyer', 'section_name': 'Requirements', 'field_name': 'budget_range', 'field_label': 'Typical Budget per Order', 'field_type': 'select', 'visibility': 'protected', 'required': False, 'searchable': False, 'options_json': ['under_25k', '25k_100k', '100k_500k', '500k_2m', '2m'], 'accepted_types_json': None, 'ordinal': 21}, {'slug': 'quality_inspector', 'section_name': 'Company', 'field_name': 'company_name', 'field_label': 'Company Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'quality_inspector', 'section_name': 'Company', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['usa', 'canada', 'mexico', 'germany', 'brazil', 'india', 'china', 'japan'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'quality_inspector', 'section_name': 'Company', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'quality_inspector', 'section_name': 'Services', 'field_name': 'service_regions', 'field_label': 'Service Regions', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['north_america', 'south_america', 'europe', 'middle_east', 'africa', 'south_asia', 'east_asia', 'southeast_asia', 'oceania'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'quality_inspector', 'section_name': 'Services', 'field_name': 'credentials', 'field_label': 'Credentials / Certificates', 'field_type': 'files', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': ['pdf'], 'ordinal': 5}, {'slug': 'rigging_logistics_provider', 'section_name': 'Company', 'field_name': 'company_name', 'field_label': 'Company Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'rigging_logistics_provider', 'section_name': 'Company', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['usa', 'canada', 'mexico', 'germany', 'brazil', 'india', 'china', 'japan'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'rigging_logistics_provider', 'section_name': 'Company', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'rigging_logistics_provider', 'section_name': 'Services', 'field_name': 'service_regions', 'field_label': 'Service Regions', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['north_america', 'south_america', 'europe', 'middle_east', 'africa', 'south_asia', 'east_asia', 'southeast_asia', 'oceania'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'rigging_logistics_provider', 'section_name': 'Services', 'field_name': 'credentials', 'field_label': 'Credentials / Certificates', 'field_type': 'files', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': ['pdf'], 'ordinal': 5}, {'slug': 'cargo_insurer', 'section_name': 'Company', 'field_name': 'company_name', 'field_label': 'Company Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'cargo_insurer', 'section_name': 'Company', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['usa', 'canada', 'mexico', 'germany', 'brazil', 'india', 'china', 'japan'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'cargo_insurer', 'section_name': 'Company', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'cargo_insurer', 'section_name': 'Services', 'field_name': 'service_regions', 'field_label': 'Service Regions', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['north_america', 'south_america', 'europe', 'middle_east', 'africa', 'south_asia', 'east_asia', 'southeast_asia', 'oceania'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'cargo_insurer', 'section_name': 'Services', 'field_name': 'credentials', 'field_label': 'Credentials / Certificates', 'field_type': 'files', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': ['pdf'], 'ordinal': 5}, {'slug': 'trade_finance_provider', 'section_name': 'Company', 'field_name': 'company_name', 'field_label': 'Company Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'trade_finance_provider', 'section_name': 'Company', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['usa', 'canada', 'mexico', 'germany', 'brazil', 'india', 'china', 'japan'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'trade_finance_provider', 'section_name': 'Company', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'trade_finance_provider', 'section_name': 'Services', 'field_name': 'service_regions', 'field_label': 'Service Regions', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['north_america', 'south_america', 'europe', 'middle_east', 'africa', 'south_asia', 'east_asia', 'southeast_asia', 'oceania'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'trade_finance_provider', 'section_name': 'Services', 'field_name': 'credentials', 'field_label': 'Credentials / Certificates', 'field_type': 'files', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': ['pdf'], 'ordinal': 5}, {'slug': 'certification_body', 'section_name': 'Company', 'field_name': 'company_name', 'field_label': 'Company Name', 'field_type': 'text', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 1}, {'slug': 'certification_body', 'section_name': 'Company', 'field_name': 'country', 'field_label': 'Country', 'field_type': 'select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['usa', 'canada', 'mexico', 'germany', 'brazil', 'india', 'china', 'japan'], 'accepted_types_json': None, 'ordinal': 2}, {'slug': 'certification_body', 'section_name': 'Company', 'field_name': 'description', 'field_label': 'About', 'field_type': 'rich_text', 'visibility': 'public', 'required': False, 'searchable': True, 'options_json': None, 'accepted_types_json': None, 'ordinal': 3}, {'slug': 'certification_body', 'section_name': 'Services', 'field_name': 'service_regions', 'field_label': 'Service Regions', 'field_type': 'multi_select', 'visibility': 'public', 'required': True, 'searchable': True, 'options_json': ['north_america', 'south_america', 'europe', 'middle_east', 'africa', 'south_asia', 'east_asia', 'southeast_asia', 'oceania'], 'accepted_types_json': None, 'ordinal': 4}, {'slug': 'certification_body', 'section_name': 'Services', 'field_name': 'credentials', 'field_label': 'Credentials / Certificates', 'field_type': 'files', 'visibility': 'private', 'required': False, 'searchable': False, 'options_json': None, 'accepted_types_json': ['pdf'], 'ordinal': 5}]
SPEC_HASH = "dbf5161a9d7aff6c730a8160b891402e2216c84c527dbbab3af8a5dea243373b"
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
    op.execute("DELETE FROM marketplace_builds WHERE spec_hash = 'dbf5161a9d7aff6c730a8160b891402e2216c84c527dbbab3af8a5dea243373b'")
    # Keep metadata tables in place to avoid destructive behavior for previous builds.
