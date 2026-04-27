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


def _admin_openapi() -> dict:
    """OpenAPI fixture exposing admin, files, ai, and bootstrap operations.

    Uses FastAPI-style auto IDs so we also exercise normalisation.
    """
    base = _minimal_openapi()
    base["paths"].update(
        {
            "/api/auth/bootstrap": {
                "post": {
                    "operationId": "bootstrap_api_auth_bootstrap_post",
                    "tags": ["auth"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/api/admin/dashboard": {
                "get": {
                    "operationId": "dashboard_api_admin_dashboard_get",
                    "tags": ["admin"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/api/admin/users": {
                "get": {
                    "operationId": "list_users_api_admin_users_get",
                    "tags": ["admin"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/api/admin/applications": {
                "get": {
                    "operationId": "list_applications_api_admin_applications_get",
                    "tags": ["admin"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/api/admin/faqs": {
                "get": {
                    "operationId": "list_faqs_api_admin_faqs_get",
                    "tags": ["admin"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/api/admin/ai/settings": {
                "get": {
                    "operationId": "get_ai_settings_api_admin_ai_settings_get",
                    "tags": ["admin"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/api/files/upload": {
                "post": {
                    "operationId": "upload_file_api_files_upload_post",
                    "tags": ["files"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/api/ai/query": {
                "post": {
                    "operationId": "query_api_ai_query_post",
                    "tags": ["ai"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/api/conversations": {
                "get": {
                    "operationId": "list_conversations_api_communication_conversations_get",
                    "tags": ["communication"],
                    "responses": {"200": {"description": "ok"}},
                },
                "post": {
                    "operationId": "create_conversation_api_communication_conversations_post",
                    "tags": ["communication"],
                    "responses": {"200": {"description": "ok"}},
                },
            },
            "/api/conversations/{conv_id}/messages": {
                "get": {
                    "operationId": "list_messages_api_communication_conversations__conv_id__messages_get",
                    "tags": ["communication"],
                    "parameters": [
                        {
                            "name": "conv_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "ok"}},
                },
                "post": {
                    "operationId": "send_message_api_communication_conversations__conv_id__messages_post",
                    "tags": ["communication"],
                    "parameters": [
                        {
                            "name": "conv_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "ok"}},
                },
            },
            "/api/notifications": {
                "get": {
                    "operationId": "list_notifications_api_notifications_get",
                    "tags": ["notifications"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/api/notifications/{notif_id}/read": {
                "post": {
                    "operationId": "mark_read_api_notifications__notif_id__read_post",
                    "tags": ["notifications"],
                    "parameters": [
                        {
                            "name": "notif_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            },
        }
    )
    return base


def _build_admin_ir() -> FrontendIR:
    config = _load_minimal_config()
    openapi_doc = _admin_openapi()
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

    def test_theme_falls_back_to_industry_preset_for_agriculture(self):
        """A marketplace whose ``industry`` mentions 'agriculture' should pick
        up the agricultural preset (earthy primary, wheat brand mark) without
        the user needing to declare a ``theme:`` block.
        """
        from compiler.parsers.yaml_config import parse_marketplace_dict

        cfg = parse_marketplace_dict({
            "marketplace": {
                "name": "GrainCo",
                "description": "Specialty grains",
                "industry": "Specialty Agriculture",
            },
            "participant_types": [],
            "profile_schemas": {},
            "onboarding": {},
        })
        assert cfg.theme.primary == "#7c5e2a"
        assert cfg.theme.logo_emoji == "🌾"
        assert cfg.theme.font == "Plus Jakarta Sans"
        assert cfg.theme.neutral == "warm"

    def test_theme_explicit_override_beats_preset(self):
        """Explicit ``theme:`` keys win over industry presets."""
        from compiler.parsers.yaml_config import parse_marketplace_dict

        cfg = parse_marketplace_dict({
            "marketplace": {
                "name": "Override",
                "description": "x",
                "industry": "agriculture",
            },
            "participant_types": [],
            "profile_schemas": {},
            "onboarding": {},
            "theme": {"primary": "#ff0000", "logo_emoji": "🟢"},
        })
        assert cfg.theme.primary == "#ff0000"   # override
        assert cfg.theme.logo_emoji == "🟢"
        # Untouched fields still come from the preset
        assert cfg.theme.font == "Plus Jakarta Sans"

    def test_scaffold_emits_themed_globals_css(self):
        """Scaffold must convert theme hex colors to HSL and inject them as
        CSS variables, plus pick up the requested font family.
        """
        from compiler.generators.scaffold import emit_scaffold
        from compiler.ir import ThemeIR

        theme = ThemeIR(
            primary="#7c5e2a",
            accent="#5a8a4a",
            neutral="warm",
            font="Plus Jakarta Sans",
            radius="lg",
            logo_emoji="🌾",
            voice="grounded",
        )
        files = emit_scaffold(theme=theme)
        css = files["src/styles/globals.css"]
        # HSL conversion happened (37 51% 33% is the rough HSL of #7c5e2a)
        assert "--primary:" in css
        assert "--accent:" in css
        assert "Plus Jakarta Sans" in css
        # Warm neutral palette landed
        assert "30 40% 99%" in css  # warm background
        # Radius lg = 0.625rem
        assert "--radius: 0.625rem" in css

        tw = files["tailwind.config.ts"]
        assert "Plus Jakarta Sans" in tw
        assert "var(--font-display)" in tw

    def test_navigation_emits_marketplace_logo_constant(self):
        """``marketplaceLogo`` should be exported alongside name/description."""
        from compiler.generators.navigation_gen import emit_navigation

        ir = _build_test_ir()
        files = emit_navigation(ir)
        nav = files["src/generated/navigation.ts"]
        assert "export const marketplaceLogo" in nav

    def test_augment_pages_with_relevant_hooks_pre_wires_each_page(self):
        """Every page's relevant ops should appear as imports + declarations
        BEFORE its AGENT_FILL marker, so the agent fill can call them.

        Uses the real OpenAPI spec so production hooks (accept/reject/edit/
        delete-message, files mutations, admin user mutations, …) are present
        in the IR — the test fixture is too sparse for these assertions.
        """
        import json
        from pathlib import Path

        from compiler.generators.hooks_gen import emit_hooks
        from compiler.generators.routes_gen import emit_routes
        from compiler.parsers.marketplace_parser import parse_marketplace
        from compiler.parsers.openapi_parser import parse_openapi
        from compiler.parsers.yaml_config import load_marketplace_yaml
        from compiler.transforms.hook_wiring import augment_pages_with_relevant_hooks
        from compiler.transforms.merge import build_frontend_ir

        repo_root = Path(__file__).resolve().parents[3]
        openapi_path = repo_root / "openapi/generated_openapi.json"
        marketplace_path = repo_root / "marketplace.yaml"
        if not openapi_path.exists() or not marketplace_path.exists():
            import pytest
            pytest.skip("Real OpenAPI / marketplace.yaml not available in this checkout")

        spec = json.loads(openapi_path.read_text())
        cfg = load_marketplace_yaml(marketplace_path)
        prod_ir = build_frontend_ir(
            parse_openapi(spec), parse_marketplace(cfg), generator_version=GENERATOR_VERSION
        )

        artifacts: dict[str, str] = {}
        artifacts.update(emit_routes(prod_ir))
        artifacts.update(emit_hooks(prod_ir))

        augmented = augment_pages_with_relevant_hooks(artifacts, prod_ir)

        thread = augmented["src/app/(dashboard)/conversations/[id]/page.tsx"]
        for hook in (
            "useSendMessage", "useEditMessage", "useDeleteMessage",
            "useAcceptConversation", "useRejectConversation",
            "useCloseConversation", "useShareAssets",
        ):
            assert hook in thread, f"{hook} missing from conversation thread page"
            assert f"= {hook}(" in thread, f"{hook} not declared in thread page"

        files_page = augmented["src/app/(dashboard)/files/page.tsx"]
        for hook in ("useUploadFile", "useDeleteFile"):
            assert hook in files_page
            assert f"= {hook}(" in files_page

        users_page = augmented["src/app/(dashboard)/admin/users/page.tsx"]
        for hook in ("useActivateUser", "useDeactivateUser", "useUpdateUserRole"):
            assert hook in users_page, f"{hook} missing from admin users page"
            assert f"= {hook}(" in users_page

        # Idempotent — second run produces the same content.
        augmented_again = augment_pages_with_relevant_hooks(augmented, prod_ir)
        assert augmented_again == augmented

    def test_query_keys_are_unique_per_operation(self):
        """Every GET operation in a module must produce a distinct queryKey,
        otherwise React Query stores responses under the same cache slot and
        one query overwrites another (the bug that hid pending applications
        on the admin dashboard).
        """
        import json
        import re
        from pathlib import Path

        from compiler.generators.hooks_gen import emit_hooks
        from compiler.parsers.marketplace_parser import parse_marketplace
        from compiler.parsers.openapi_parser import parse_openapi
        from compiler.parsers.yaml_config import load_marketplace_yaml
        from compiler.transforms.merge import build_frontend_ir

        repo_root = Path(__file__).resolve().parents[3]
        spec_path = repo_root / "openapi/generated_openapi.json"
        marketplace_path = repo_root / "marketplace.yaml"
        if not spec_path.exists() or not marketplace_path.exists():
            import pytest
            pytest.skip("Real spec not available in this checkout")

        spec = json.loads(spec_path.read_text())
        cfg = load_marketplace_yaml(marketplace_path)
        ir = build_frontend_ir(parse_openapi(spec), parse_marketplace(cfg), generator_version=GENERATOR_VERSION)
        files = emit_hooks(ir)

        # Pull every key-factory entry and confirm none collapse to the
        # same array literal. We do this textually because the factory body
        # is small and stable.
        for path, content in files.items():
            for match in re.finditer(
                r"(\w+):\s*\(?[^)]*\)?\s*=>\s*(\[[^\]]+\])",
                content,
            ):
                pass  # extraction is via the assertion below
            # Collect every right-hand-side array literal in this file's keys block.
            keys_block = re.search(
                r"export const \w+Keys = \{([^}]+)\}",
                content,
                re.DOTALL,
            )
            if not keys_block:
                continue
            literals = re.findall(r"=>\s*(\[[^\]]+\])", keys_block.group(1))
            # Replace path-param placeholders with stable strings so we
            # compare structural shape, not the parameter name.
            normalized = [re.sub(r"\b[a-z_]+_id\b", '"<id>"', lit) for lit in literals]
            duplicates = {lit for lit in normalized if normalized.count(lit) > 1}
            assert not duplicates, (
                f"Duplicate queryKey shapes in {path}: {duplicates}"
            )

    def test_jsonlist_emits_as_array_type(self):
        """The OpenAPI ``JSONList`` schema is ``type: 'array'`` — the TS type
        emitted must be an array, not ``Record<string, unknown>``.
        """
        import json
        from pathlib import Path

        from compiler.generators.types_gen import emit_types
        from compiler.parsers.marketplace_parser import parse_marketplace
        from compiler.parsers.openapi_parser import parse_openapi
        from compiler.parsers.yaml_config import load_marketplace_yaml
        from compiler.transforms.merge import build_frontend_ir

        repo_root = Path(__file__).resolve().parents[3]
        spec_path = repo_root / "openapi/generated_openapi.json"
        marketplace_path = repo_root / "marketplace.yaml"
        if not spec_path.exists() or not marketplace_path.exists():
            import pytest
            pytest.skip("Real spec not available in this checkout")

        spec = json.loads(spec_path.read_text())
        cfg = load_marketplace_yaml(marketplace_path)
        ir = build_frontend_ir(parse_openapi(spec), parse_marketplace(cfg), generator_version=GENERATOR_VERSION)
        types_ts = emit_types(ir)["src/generated/types.ts"]
        assert "export type JSONList = Array<" in types_ts
        # JSONObject stays an object — make sure we didn't break it.
        assert "export type JSONObject = Record<string, unknown>" in types_ts

    def test_admin_operations_get_admin_qualified_when_colliding(self):
        """Admin endpoints whose name collides with a user-facing one must be
        prefixed (``getProfile`` → ``getAdminProfile``) so the generated client
        + hook layers expose both — otherwise admin endpoints silently shadow.
        """
        from compiler.transforms.merge import (
            _admin_qualified_id,
            _disambiguate_admin_collisions,
        )
        from compiler.ir import OperationIR

        assert _admin_qualified_id("getProfile") == "getAdminProfile"
        assert _admin_qualified_id("listConversations") == "listAdminConversations"
        assert _admin_qualified_id("deleteDocument") == "deleteAdminDocument"
        assert _admin_qualified_id("updatePrompt") == "updateAdminPrompt"

        def _op(op_id: str, module: str, path: str) -> OperationIR:
            return OperationIR(
                id=op_id, entity_slug=None, module=module, kind=op_id,
                method="GET", path=path, request_schema=None, response_schema=None,
                auth_required=False, path_params=(), query_params=(),
            )

        ops = [
            _op("getProfile", "admin", "/api/admin/profiles/{profile_id}"),
            _op("getProfile", "profiles", "/api/profiles/{type_slug}/{profile_id}"),
            _op("listConversations", "admin", "/api/admin/conversations"),
            _op("listConversations", "communication", "/api/conversations"),
            _op("login", "auth", "/api/auth/login"),  # no collision
        ]
        result = _disambiguate_admin_collisions(ops)
        ids = {(o.module, o.id) for o in result}
        assert ("admin", "getAdminProfile") in ids
        assert ("profiles", "getProfile") in ids
        assert ("admin", "listAdminConversations") in ids
        assert ("communication", "listConversations") in ids
        assert ("auth", "login") in ids
        # Total unique ids must equal len(ops): no collisions remain.
        all_ids = [o.id for o in result]
        assert len(set(all_ids)) == len(ops)

    def test_build_ir_creates_pages(self):
        ir = _build_test_ir()
        page_ids = {p.id for p in ir.pages}
        assert "login" in page_ids
        assert "dashboard" in page_ids
        assert "profile-edit" in page_ids
        assert "search" in page_ids

    def test_admin_subpages_emitted_when_admin_ops_present(self):
        """F1.9 — admin/users, admin/applications, admin/faqs, admin/ai routes."""
        ir = _build_admin_ir()
        page_ids = {p.id for p in ir.pages}
        assert "admin-dashboard" in page_ids
        assert "admin-users" in page_ids
        assert "admin-applications" in page_ids
        assert "admin-faqs" in page_ids
        assert "admin-ai" in page_ids

    def test_files_and_ai_chat_pages_emitted_when_modules_present(self):
        """F1.10 — files manager + AI chat pages."""
        ir = _build_admin_ir()
        page_ids = {p.id for p in ir.pages}
        assert "files" in page_ids
        assert "ai-chat" in page_ids

    def test_bootstrap_page_emitted_when_bootstrap_op_present(self):
        """F1.4 — bootstrap auth page."""
        ir = _build_admin_ir()
        page_ids = {p.id for p in ir.pages}
        assert "bootstrap" in page_ids

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
        assert "API explorer" in content
        assert "Terminal" in content


class TestOperationsManifestGenerator:
    def test_emits_operations_manifest(self):
        from compiler.generators.operations_manifest_gen import emit_operations_manifest

        ir = _build_test_ir()
        files = emit_operations_manifest(ir)
        assert "src/generated/operations-manifest.ts" in files
        c = files["src/generated/operations-manifest.ts"]
        assert "export const operationsManifest" in c
        assert "OperationManifestEntry" in c


class TestApiExplorerGenerator:
    def test_emits_api_explorer_page(self):
        from compiler.generators.api_explorer_gen import emit_api_explorer_page

        ir = _build_test_ir()
        files = emit_api_explorer_page(ir)
        assert "src/app/(dashboard)/dev/api-explorer/page.tsx" in files
        assert "operationsManifest" in files["src/app/(dashboard)/dev/api-explorer/page.tsx"]


# ── F1 phase: page stubs + AGENT_FILL marker coverage ────────────────


class TestF1PageStubs:
    """Verify Phase F1.1/F1.4–F1.10 — every stub page is emitted with markers."""

    def test_every_route_page_carries_a_marker(self):
        from compiler.agent_markers import find_fill_markers
        from compiler.generators.routes_gen import emit_routes

        ir = _build_test_ir()
        files = emit_routes(ir)

        page_files = [
            path for path in files
            if path.startswith("src/app/")
            and path.endswith("/page.tsx")
            and "/layout.tsx" not in path
        ]
        assert page_files, "expected at least one generated page"

        # Pages that intentionally rely on Next.js redirect (no UI content).
        markerless_pages = {
            "src/app/page.tsx",
            # Role-router that redirects to /dashboard/{supply,demand} or /admin
            "src/app/(dashboard)/dashboard/page.tsx",
        }

        missing: list[str] = []
        for path in page_files:
            if path in markerless_pages:
                continue
            markers = find_fill_markers(files[path])
            if not markers:
                missing.append(path)

        assert not missing, (
            f"expected an AGENT_FILL marker in every stub page, missing in: {missing}"
        )

    def test_marker_ids_are_unique_per_file(self):
        from compiler.agent_markers import find_fill_markers
        from compiler.generators.routes_gen import emit_routes

        ir = _build_test_ir()
        files = emit_routes(ir)
        for path, content in files.items():
            if not (path.startswith("src/app/") and path.endswith("/page.tsx")):
                continue
            ids = [m.marker_id for m in find_fill_markers(content)]
            assert len(ids) == len(set(ids)), (
                f"duplicate AGENT_FILL marker ids in {path}: {ids}"
            )

    def test_dashboard_router_redirects_by_role(self):
        """``/dashboard`` is a thin role-router (F1.5) — no marker, redirects."""
        from compiler.agent_markers import find_fill_markers
        from compiler.generators.routes_gen import emit_routes

        ir = _build_test_ir()
        files = emit_routes(ir)
        page = files["src/app/(dashboard)/dashboard/page.tsx"]
        assert "useRouter" in page
        assert "/dashboard/supply" in page
        assert "/dashboard/demand" in page
        assert 'router.replace("/admin")' in page
        assert "participantTypes" in page
        assert find_fill_markers(page) == []

    def test_supply_and_demand_dashboards_emitted_with_markers(self):
        """F1.5 — supply / demand pages exist with role-scoped AGENT_FILL markers."""
        from compiler.agent_markers import find_fill_markers
        from compiler.generators.routes_gen import emit_routes

        ir = _build_test_ir()
        files = emit_routes(ir)

        supply = files["src/app/(dashboard)/dashboard/supply/page.tsx"]
        demand = files["src/app/(dashboard)/dashboard/demand/page.tsx"]

        supply_ids = [m.marker_id for m in find_fill_markers(supply)]
        demand_ids = [m.marker_id for m in find_fill_markers(demand)]
        assert "supply_dashboard_main" in supply_ids
        assert "demand_dashboard_main" in demand_ids
        # Each role-specific dashboard renders the shared stats hooks.
        for page in (supply, demand):
            assert "useCurrentProfile" in page
            assert "useListConversations" in page
            assert "useListNotifications" in page

    def test_role_dashboards_skipped_when_role_absent(self):
        """Marketplaces with only one side should not emit the missing role page."""
        from dataclasses import replace

        from compiler.generators.routes_gen import emit_routes

        ir = _build_test_ir()
        # Drop the demand-side entity so no entity carries role="demand".
        supply_only = tuple(e for e in ir.entities if e.role == "supply")
        ir = replace(ir, entities=supply_only)
        files = emit_routes(ir)
        assert "src/app/(dashboard)/dashboard/supply/page.tsx" in files
        assert "src/app/(dashboard)/dashboard/demand/page.tsx" not in files

    def test_profile_view_calls_current_profile_hook(self):
        from compiler.generators.routes_gen import emit_routes

        ir = _build_test_ir()
        files = emit_routes(ir)
        page = files["src/app/(dashboard)/profile/page.tsx"]
        assert "useCurrentProfile" in page

    def test_conversations_list_uses_react_query_hook(self):
        from compiler.generators.routes_gen import emit_routes

        ir = _build_admin_ir()
        files = emit_routes(ir)
        page = files["src/app/(dashboard)/conversations/page.tsx"]
        assert "useListConversations" in page
        assert "useCreateConversation" in page

    def test_conversation_detail_loads_message_history(self):
        from compiler.generators.routes_gen import emit_routes

        ir = _build_admin_ir()
        files = emit_routes(ir)
        detail = files["src/app/(dashboard)/conversations/[id]/page.tsx"]
        assert "useListMessages" in detail
        assert "useConversationWebSocket" in detail

    def test_notifications_page_invokes_mark_read(self):
        from compiler.generators.routes_gen import emit_routes

        ir = _build_admin_ir()
        files = emit_routes(ir)
        page = files["src/app/(dashboard)/notifications/page.tsx"]
        assert "useListNotifications" in page
        assert "useMarkRead" in page
        assert "markRead.mutate(id)" in page

    def test_search_page_uses_search_mutation(self):
        from compiler.generators.routes_gen import emit_routes

        ir = _build_test_ir()
        files = emit_routes(ir)
        page = files["src/app/(dashboard)/search/page.tsx"]
        assert "useSearch" in page
        assert "search.mutateAsync" in page


class TestAuthMiddleware:
    """Phase F1 closure — the generated app must gate dashboard routes."""

    def test_emits_middleware_file(self):
        from compiler.generators.routes_gen import emit_routes

        ir = _build_test_ir()
        files = emit_routes(ir)
        assert "src/middleware.ts" in files

    def test_middleware_redirects_when_session_cookie_missing(self):
        from compiler.generators.routes_gen import emit_routes

        ir = _build_test_ir()
        files = emit_routes(ir)
        mw = files["src/middleware.ts"]
        assert 'request.cookies.get("session_token")' in mw
        assert "NextResponse.redirect" in mw
        # Login/signup must remain reachable without a cookie.
        assert '"/login"' in mw
        assert "_next" in mw

    def test_middleware_preserves_intended_destination(self):
        from compiler.generators.routes_gen import emit_routes

        ir = _build_test_ir()
        mw = emit_routes(ir)["src/middleware.ts"]
        assert 'searchParams.set("next"' in mw


class TestProfileFormWiring:
    """The profile edit form must persist drafts via the API."""

    def test_profile_form_uses_draft_hooks(self):
        from compiler.generators.components_gen import emit_components

        ir = _build_test_ir()
        files = emit_components(ir)
        form = files["src/components/forms/profile-form.tsx"]
        assert "useDraft" in form
        assert "useUpdateDraft" in form
        assert "useRegister" in form
        assert "updateDraft.mutateAsync" in form
        assert "registerProfile.mutateAsync" in form


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
