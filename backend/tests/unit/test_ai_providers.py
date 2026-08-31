"""Tests for multi-provider AI abstraction, config resolution, and client factory."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ServiceUnavailableError
from app.modules.ai.providers import PROVIDER_REGISTRY, ProviderID


# ── Provider Registry ────────────────────────────────────────────────────


class TestProviderRegistry:
    def test_all_providers_registered(self):
        assert ProviderID.openai in PROVIDER_REGISTRY
        assert ProviderID.openrouter in PROVIDER_REGISTRY
        assert ProviderID.gemini in PROVIDER_REGISTRY

    def test_openai_spec(self):
        spec = PROVIDER_REGISTRY[ProviderID.openai]
        assert spec.base_url is None
        assert spec.supports_embeddings is True
        assert spec.api_key_env_name == "openai_api_key"

    def test_openrouter_spec(self):
        spec = PROVIDER_REGISTRY[ProviderID.openrouter]
        assert spec.base_url == "https://openrouter.ai/api/v1"
        # OpenRouter now proxies OpenAI embeddings (openai/text-embedding-3-small, 1536-dim).
        assert spec.supports_embeddings is True
        assert spec.default_embedding_model == "openai/text-embedding-3-small"
        assert spec.default_embedding_dimensions == 1536

    def test_gemini_spec(self):
        spec = PROVIDER_REGISTRY[ProviderID.gemini]
        assert "generativelanguage" in spec.base_url
        assert spec.supports_embeddings is True


# ── Client Factory ───────────────────────────────────────────────────────


class TestClientFactory:
    @patch("app.modules.ai.client_factory.settings")
    def test_get_chat_client_openai(self, mock_settings):
        mock_settings.openai_api_key = "sk-test"
        from app.modules.ai.client_factory import get_chat_client

        client = get_chat_client("openai")
        assert client is not None

    @patch("app.modules.ai.client_factory.settings")
    def test_get_chat_client_missing_key(self, mock_settings):
        mock_settings.openai_api_key = ""
        from app.modules.ai.client_factory import get_chat_client

        with pytest.raises(ServiceUnavailableError, match="API key not configured"):
            get_chat_client("openai")

    @patch("app.modules.ai.client_factory.settings")
    def test_get_chat_client_unknown_provider(self, mock_settings):
        from app.modules.ai.client_factory import get_chat_client

        with pytest.raises(ServiceUnavailableError, match="Unknown AI provider"):
            get_chat_client("nonexistent")

    @patch("app.modules.ai.client_factory.settings")
    def test_get_embedding_client_openrouter(self, mock_settings):
        # OpenRouter now supports embeddings, so a client should be returned.
        mock_settings.openrouter_api_key = "or-test"
        from app.modules.ai.client_factory import get_embedding_client

        client = get_embedding_client("openrouter")
        assert client is not None

    @patch("app.modules.ai.client_factory.settings")
    def test_get_embedding_client_openai(self, mock_settings):
        mock_settings.openai_api_key = "sk-test"
        from app.modules.ai.client_factory import get_embedding_client

        client = get_embedding_client("openai")
        assert client is not None


# ── Config Resolution ────────────────────────────────────────────────────


class TestResolvedChatConfig:
    @pytest.mark.asyncio
    @patch("app.modules.ai.repository.get_llm_settings", new_callable=AsyncMock)
    async def test_defaults_when_no_settings(self, mock_get):
        mock_get.return_value = None
        from app.modules.ai.repository import get_resolved_chat_config

        config = await get_resolved_chat_config()
        assert config["provider"] == "openrouter"
        assert config["model"] == "openai/gpt-4o-mini"
        assert config["temperature"] == 0.7
        assert config["max_tokens"] == 1024

    @pytest.mark.asyncio
    @patch("app.modules.ai.repository.get_llm_settings", new_callable=AsyncMock)
    async def test_reads_new_schema(self, mock_get):
        mock_get.return_value = {
            "chat_provider": "openrouter",
            "chat_model": "meta-llama/llama-3-8b",
            "temperature": 0.5,
            "max_tokens": 2048,
        }
        from app.modules.ai.repository import get_resolved_chat_config

        config = await get_resolved_chat_config()
        assert config["provider"] == "openrouter"
        assert config["model"] == "meta-llama/llama-3-8b"

    @pytest.mark.asyncio
    @patch("app.modules.ai.repository.get_llm_settings", new_callable=AsyncMock)
    async def test_legacy_schema_backward_compat(self, mock_get):
        mock_get.return_value = {
            "model": "gpt-4o",
            "temperature": 0.3,
            "max_tokens": 512,
        }
        from app.modules.ai.repository import get_resolved_chat_config

        config = await get_resolved_chat_config()
        assert config["provider"] == "openrouter"
        assert config["model"] == "gpt-4o"
        assert config["temperature"] == 0.3

    @pytest.mark.asyncio
    @patch("app.modules.ai.repository.get_llm_settings", new_callable=AsyncMock)
    async def test_use_case_override(self, mock_get):
        mock_get.return_value = {
            "chat_provider": "openai",
            "chat_model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 1024,
            "use_case_overrides": {
                "rag_query": {"provider": "gemini", "model": "gemini-2.0-flash"},
                "follow_up": None,
            },
        }
        from app.modules.ai.repository import get_resolved_chat_config

        config = await get_resolved_chat_config("rag_query")
        assert config["provider"] == "gemini"
        assert config["model"] == "gemini-2.0-flash"

    @pytest.mark.asyncio
    @patch("app.modules.ai.repository.get_llm_settings", new_callable=AsyncMock)
    async def test_null_override_uses_global(self, mock_get):
        mock_get.return_value = {
            "chat_provider": "openai",
            "chat_model": "gpt-4o-mini",
            "temperature": 0.7,
            "max_tokens": 1024,
            "use_case_overrides": {
                "follow_up": None,
            },
        }
        from app.modules.ai.repository import get_resolved_chat_config

        config = await get_resolved_chat_config("follow_up")
        assert config["provider"] == "openai"
        assert config["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    @patch("app.modules.ai.repository.get_llm_settings", new_callable=AsyncMock)
    async def test_document_extraction_has_a_schema_reliable_default(self, mock_get):
        """Field extraction needs strict JSON-schema output, so it defaults to a cheap
        schema-reliable model even with no settings stored."""
        mock_get.return_value = None
        from app.modules.ai.repository import get_resolved_chat_config

        config = await get_resolved_chat_config("document_extraction")
        assert config["provider"] == "openrouter"
        assert config["model"] == "google/gemini-2.0-flash-001"

    @pytest.mark.asyncio
    @patch("app.modules.ai.repository.get_llm_settings", new_callable=AsyncMock)
    async def test_use_case_default_beats_global_setting(self, mock_get):
        """A global chat model an operator set is not thereby their choice for extraction."""
        mock_get.return_value = {"chat_provider": "openai", "chat_model": "gpt-4o"}
        from app.modules.ai.repository import get_resolved_chat_config

        config = await get_resolved_chat_config("document_extraction")
        assert config["model"] == "google/gemini-2.0-flash-001"

    @pytest.mark.asyncio
    @patch("app.modules.ai.repository.get_llm_settings", new_callable=AsyncMock)
    async def test_explicit_override_still_beats_use_case_default(self, mock_get):
        mock_get.return_value = {
            "chat_provider": "openrouter",
            "chat_model": "openai/gpt-4o-mini",
            "use_case_configs": {
                "document_extraction": {"provider": "openai", "model": "gpt-4o"},
            },
        }
        from app.modules.ai.repository import get_resolved_chat_config

        config = await get_resolved_chat_config("document_extraction")
        assert config["provider"] == "openai"
        assert config["model"] == "gpt-4o"


class TestEmbeddingConfig:
    @pytest.mark.asyncio
    @patch("app.modules.ai.repository.get_llm_settings", new_callable=AsyncMock)
    async def test_defaults(self, mock_get):
        mock_get.return_value = None
        from app.modules.ai.repository import get_embedding_config

        config = await get_embedding_config()
        assert config["provider"] == "openai"
        assert config["model"] == "text-embedding-3-small"
        assert config["dimensions"] == 1536

    @pytest.mark.asyncio
    @patch("app.modules.ai.repository.get_llm_settings", new_callable=AsyncMock)
    async def test_custom_settings(self, mock_get):
        mock_get.return_value = {
            "embedding_provider": "gemini",
            "embedding_model": "text-embedding-004",
            "embedding_dimensions": 768,
        }
        from app.modules.ai.repository import get_embedding_config

        config = await get_embedding_config()
        assert config["provider"] == "gemini"
        assert config["model"] == "text-embedding-004"
        assert config["dimensions"] == 768


# ── Settings Migration ───────────────────────────────────────────────────


class TestSettingsMigration:
    @pytest.mark.asyncio
    @patch("app.modules.ai.settings_migration.repo")
    async def test_migration_skips_when_no_settings(self, mock_repo):
        mock_repo.get_llm_settings = AsyncMock(return_value=None)
        from app.modules.ai.settings_migration import migrate_llm_settings

        await migrate_llm_settings()
        mock_repo.upsert_llm_settings.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.modules.ai.settings_migration.repo")
    async def test_migration_skips_when_already_migrated(self, mock_repo):
        mock_repo.get_llm_settings = AsyncMock(
            return_value={"chat_provider": "openai", "chat_model": "gpt-4o"}
        )
        from app.modules.ai.settings_migration import migrate_llm_settings

        await migrate_llm_settings()
        mock_repo.upsert_llm_settings.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.modules.ai.settings_migration.repo")
    async def test_migration_converts_legacy_settings(self, mock_repo):
        mock_repo.get_llm_settings = AsyncMock(
            return_value={
                "model": "gpt-4o",
                "temperature": 0.5,
                "max_tokens": 2048,
            }
        )
        mock_repo.upsert_llm_settings = AsyncMock()
        from app.modules.ai.settings_migration import migrate_llm_settings

        await migrate_llm_settings()
        mock_repo.upsert_llm_settings.assert_called_once()
        args = mock_repo.upsert_llm_settings.call_args[0][0]
        assert args["chat_provider"] == "openrouter"
        assert args["chat_model"] == "openai/gpt-4o"
        assert args["temperature"] == 0.5
        assert args["max_tokens"] == 2048
        assert args["embedding_provider"] == "openai"
        assert args["enabled_providers"] == ["openrouter", "openai"]


# ── LLM Client ───────────────────────────────────────────────────────────


class TestLLMClient:
    @pytest.mark.asyncio
    @patch("app.modules.ai.llm_client.get_chat_client")
    @patch("app.modules.ai.llm_client.repo")
    async def test_generate_passes_use_case(self, mock_repo, mock_factory):
        mock_repo.get_resolved_chat_config = AsyncMock(
            return_value={
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.7,
                "max_tokens": 1024,
            }
        )
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="test response"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_factory.return_value = mock_client

        from app.modules.ai.llm_client import generate

        result = await generate([{"role": "user", "content": "hi"}], use_case="rag_query")
        assert result == "test response"
        mock_repo.get_resolved_chat_config.assert_called_once_with("rag_query")
        mock_factory.assert_called_once_with("openai")
