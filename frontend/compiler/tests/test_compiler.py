"""Unit tests for the frontend compiler pipeline."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from compiler.constants import GENERATOR_VERSION
from compiler.generators.scaffold import emit_scaffold
from compiler.generators.types_gen import emit_types
from compiler.generators.schemas_gen import emit_schemas
from compiler.generators.api_client_gen import emit_api_clients
from compiler.generators.hooks_gen import emit_hooks
from compiler.generators.navigation_gen import emit_navigation
from compiler.ir import FrontendIR
from compiler.naming import (
    hook_name,
    operation_id,
    slug_to_camel,
    slug_to_kebab,
    slug_to_pascal,
)
from compiler.parsers.marketplace_parser import parse_marketplace
from compiler.parsers.openapi_parser import parse_openapi
from compiler.parsers.yaml_config import MarketplaceYaml, parse_marketplace_dict
from compiler.transforms.merge import build_frontend_ir
from compiler.writer import write_frontend

# ── Fixtures ──────────────────────────────────────────────────────────

MINIMAL_CONFIG_DICT = {
    "marketplace": {"name": "TestMkt", "description": "Test", "industry": "Test"},
    "participant_types": [
        {
            "name": "Seller",
            "slug": "seller",
            "role": "supply",
            "permissions": {"can_search": False, "visible_in_search": True},
        },
        {
            "name": "Buyer",
            "slug": "buyer",
            "role": "demand",
            "permissions": {"can_search": True, "visible_in_search": False},
        },
    ],
    "profile_schemas": {
        "seller": {
            "sections": [
                {
                    "name": "Info",
                    "fields": [
                        {
                            "name": "company",
                            "label": "Company",
                            "type": "text",
                            "required": True,
                        }
                    ],
                }
            ]
        },
        "buyer": {
            "sections": [
                {
                    "name": "Info",
                    "fields": [
                        {
                            "name": "org_name",
                            "label": "Organization",
                            "type": "text",
                            "required": True,
                        }
                    ],
                }
            ]
        },
    },
    "onboarding": {
        "seller": {"requires_approval": True, "approval_type": "manual"},
        "buyer": {"requires_approval": False, "approval_type": "auto"},
    },
    "communication": {
        "conversation_rules": [{"initiator": "buyer", "receiver": "seller"}]
    },
    "discovery": {
        "searchable_types": ["seller"],
        "filter_fields": [],
    },
}


def _load_minimal_config() -> MarketplaceYaml:
    return parse_marketplace_dict(MINIMAL_CONFIG_DICT)


def _minimal_openapi() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Test", "version": "1.0.0"},
        "paths": {
            "/api/auth/login": {
                "post": {
                    "operationId": "login",
                    "tags": ["auth"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/LoginRequest"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/AuthResponse"}
                                }
                            }
                        }
                    },
                }
            },
            "/api/roles/seller/draft": {
                "get": {
                    "operationId": "getSellerDraft",
                    "tags": ["profiles"],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/SellerDraftResponse"
                                    }
                                }
                            }
                        }
                    },
                },
                "put": {
                    "operationId": "updateSellerDraft",
                    "tags": ["profiles"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/SellerDraftUpdateRequest"
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/SellerDraftResponse"
                                    }
                                }
                            }
                        }
                    },
                },
            },
        },
        "components": {
            "schemas": {
                "LoginRequest": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string"},
                        "password": {"type": "string"},
                    },
                    "required": ["email", "password"],
                },
                "AuthResponse": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "email": {"type": "string"},
                    },
                    "required": ["user_id", "email"],
                },
                "SellerDraftResponse": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "fields": {"type": "object"},
                    },
                    "required": ["id", "fields"],
                },
                "SellerDraftUpdateRequest": {
                    "type": "object",
                    "properties": {
                        "fields": {"type": "object"},
                    },
                    "required": ["fields"],
                },
            }
        },
    }


def _build_test_ir() -> FrontendIR:
    config = _load_minimal_config()
    openapi_doc = _minimal_openapi()
    raw_openapi = parse_openapi(openapi_doc)
    raw_marketplace = parse_marketplace(config)
    return build_frontend_ir(raw_openapi, raw_marketplace, generator_version=GENERATOR_VERSION)


# ── Naming tests ──────────────────────────────────────────────────────


class TestNaming:
    def test_slug_to_pascal(self):
        assert slug_to_pascal("producer") == "Producer"
        assert slug_to_pascal("primary_crops") == "PrimaryCrops"
        assert slug_to_pascal("my-kebab") == "MyKebab"

    def test_slug_to_camel(self):
        assert slug_to_camel("get_producer_draft") == "getProducerDraft"
        assert slug_to_camel("producer") == "producer"

    def test_slug_to_kebab(self):
        assert slug_to_kebab("primary_crops") == "primary-crops"

    def test_operation_id(self):
        assert operation_id("getDraft", "producer") == "getProducerDraft"
        assert operation_id("register", "buyer") == "registerBuyer"

    def test_hook_name(self):
        assert hook_name("getProducerDraft") == "useProducerDraft"
        assert hook_name("updateProducerDraft") == "useUpdateProducerDraft"


# ── Parser tests ──────────────────────────────────────────────────────


class TestOpenAPIParser:
    def test_parse_extracts_operations(self):
        doc = _minimal_openapi()
        result = parse_openapi(doc)
        assert len(result.operations) == 3
        op_ids = {o.operation_id for o in result.operations}
        assert "login" in op_ids
        assert "getSellerDraft" in op_ids

    def test_parse_extracts_schemas(self):
        doc = _minimal_openapi()
        result = parse_openapi(doc)
        assert "LoginRequest" in result.schemas
        assert "AuthResponse" in result.schemas


class TestMarketplaceParser:
    def test_parse_extracts_entities(self):
        config = _load_minimal_config()
        result = parse_marketplace(config)
        assert len(result.entities) == 2
        slugs = {e.slug for e in result.entities}
        assert slugs == {"seller", "buyer"}

    def test_parse_extracts_fields(self):
        config = _load_minimal_config()
        result = parse_marketplace(config)
        seller = next(e for e in result.entities if e.slug == "seller")
        assert len(seller.sections) == 1
        assert seller.sections[0].fields[0].name == "company"


# ── IR + Transform tests ─────────────────────────────────────────────


class TestMergeTransform:
    def test_build_ir_creates_entities(self):
        ir = _build_test_ir()
        assert len(ir.entities) == 2

    def test_build_ir_creates_operations(self):
        ir = _build_test_ir()
        assert len(ir.operations) > 0
        op_ids = {o.id for o in ir.operations}
        assert "getSellerDraft" in op_ids

    def test_build_ir_creates_pages(self):
        ir = _build_test_ir()
        page_ids = {p.id for p in ir.pages}
        assert "login" in page_ids
        assert "dashboard" in page_ids
        assert "profile-edit" in page_ids
        assert "search" in page_ids

    def test_build_ir_creates_navigation(self):
        ir = _build_test_ir()
        labels = {item.label for item in ir.navigation.items}
        assert "Dashboard" in labels
        assert "Search" in labels
        assert "My Profile" in labels

    def test_spec_hash_is_stable(self):
        ir1 = _build_test_ir()
        ir2 = _build_test_ir()
        assert ir1.spec_hash == ir2.spec_hash


# ── Generator tests ───────────────────────────────────────────────────


class TestScaffoldGenerator:
    def test_emits_package_json(self):
        files = emit_scaffold()
        assert "package.json" in files
        pkg = json.loads(files["package.json"])
        assert pkg["name"] == "cosolvent-frontend"
        assert "next" in pkg["dependencies"]

    def test_emits_tsconfig(self):
        files = emit_scaffold()
        assert "tsconfig.json" in files


class TestTypesGenerator:
    def test_emits_types_file(self):
        ir = _build_test_ir()
        files = emit_types(ir)
        assert "src/generated/types.ts" in files
        content = files["src/generated/types.ts"]
        assert "SellerDraftFields" in content
        assert "BuyerDraftFields" in content
        assert "ProfileStatus" in content

    def test_contains_entity_fields(self):
        ir = _build_test_ir()
        files = emit_types(ir)
        content = files["src/generated/types.ts"]
        assert "company: string;" in content


class TestSchemasGenerator:
    def test_emits_schemas_file(self):
        ir = _build_test_ir()
        files = emit_schemas(ir)
        assert "src/generated/schemas.ts" in files
        content = files["src/generated/schemas.ts"]
        assert "sellerDraftFieldsSchema" in content
        assert "z.object" in content

    def test_required_fields_have_validation(self):
        ir = _build_test_ir()
        files = emit_schemas(ir)
        content = files["src/generated/schemas.ts"]
        assert '.min(1, "Company is required")' in content


class TestApiClientGenerator:
    def test_emits_base_client(self):
        ir = _build_test_ir()
        files = emit_api_clients(ir)
        assert "src/generated/api/client.ts" in files
        assert "apiFetch" in files["src/generated/api/client.ts"]

    def test_emits_module_clients(self):
        ir = _build_test_ir()
        files = emit_api_clients(ir)
        assert "src/generated/api/profiles.ts" in files
        assert "src/generated/api/auth.ts" in files


class TestHooksGenerator:
    def test_emits_hook_files(self):
        ir = _build_test_ir()
        files = emit_hooks(ir)
        assert "src/generated/hooks/use-profiles.ts" in files


class TestNavigationGenerator:
    def test_emits_navigation(self):
        ir = _build_test_ir()
        files = emit_navigation(ir)
        assert "src/generated/navigation.ts" in files
        content = files["src/generated/navigation.ts"]
        assert "Dashboard" in content
        assert "Search" in content
        assert '"seller"' in content


# ── Writer tests ──────────────────────────────────────────────────────


class TestWriter:
    def test_writes_files_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_frontend(
                Path(tmpdir),
                {"src/generated/types.ts": "export type A = string;", "README.md": "# Hi"},
                spec_hash="abc123",
                generator_version="1.0.0",
            )
            assert "src/generated/types.ts" in result["generated"]
            assert (Path(tmpdir) / ".generated-manifest.json").exists()

    def test_skips_existing_non_managed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            readme = Path(tmpdir) / "README.md"
            readme.write_text("original")

            write_frontend(
                Path(tmpdir),
                {"README.md": "overwritten", "src/generated/types.ts": "export type A = string;"},
                spec_hash="abc",
                generator_version="1.0.0",
            )
            assert readme.read_text() == "original"

    def test_regenerates_managed_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            types_path = Path(tmpdir) / "src" / "generated" / "types.ts"
            types_path.parent.mkdir(parents=True)
            types_path.write_text("old content")

            write_frontend(
                Path(tmpdir),
                {"src/generated/types.ts": "new content"},
                spec_hash="abc",
                generator_version="1.0.0",
            )
            assert types_path.read_text() == "new content"


# ── Full pipeline test ────────────────────────────────────────────────


class TestFullPipeline:
    def test_compile_frontend_minimal(self):
        from compiler.service import compile_frontend

        with tempfile.TemporaryDirectory() as tmpdir:
            openapi_path = Path(tmpdir) / "openapi.json"
            marketplace_path = Path(tmpdir) / "marketplace.yaml"
            output_path = Path(tmpdir) / "frontend"

            openapi_path.write_text(json.dumps(_minimal_openapi()))

            import yaml

            marketplace_path.write_text(
                yaml.dump(MINIMAL_CONFIG_DICT, default_flow_style=False)
            )

            result = compile_frontend(
                openapi_path=openapi_path,
                marketplace_path=marketplace_path,
                output_dir=output_path,
            )

            assert result["ok"] is True
            assert len(result["generated"]) > 30
            assert (output_path / "package.json").exists()
            assert (output_path / "src" / "generated" / "types.ts").exists()
            assert (output_path / "src" / "generated" / "schemas.ts").exists()
            assert (output_path / "src" / "generated" / "api" / "client.ts").exists()
