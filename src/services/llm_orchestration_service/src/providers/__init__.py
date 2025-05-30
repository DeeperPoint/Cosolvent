# providers/__init__.py
from typing import Dict, Type
from .base import LLMClient
from .openai_client import OpenAIClient
from .google_client import GoogleClient
from .hf_client import HuggingFaceClient
from ..config.models import ProviderConfig
from ..core.exceptions import ProviderNotFoundException

# Registry of available provider clients
_provider_clients: Dict[str, Type[LLMClient]] = {
    "openai": OpenAIClient,
    "google": GoogleClient,
    "huggingface": HuggingFaceClient,
    # Add other providers here as they are implemented
}

# Cache for instantiated clients to reuse them
_client_instances: Dict[str, LLMClient] = {}

async def get_client(provider_name: str, config: ProviderConfig) -> LLMClient:
    """
    Factory function to get an initialized LLM client instance.
    Caches instances to avoid re-initializing on every call.
    """
    normalized_provider_name = provider_name.lower()

    if normalized_provider_name in _client_instances:
        # TODO: Add logic to check if config has changed and re-initialize if necessary
        return _client_instances[normalized_provider_name]

    if normalized_provider_name not in _provider_clients:
        raise ProviderNotFoundException(provider_name)

    client_class = _provider_clients[normalized_provider_name]
    # Pass the specific provider_config to the client constructor
    instance = client_class(config=config)
    _client_instances[normalized_provider_name] = instance
    return instance

def register_provider(name: str, client_class: Type[LLMClient]):
    """Allows dynamic registration of new providers."""
    _provider_clients[name.lower()] = client_class

# Example of how services might get a client:
# from ..config.store import get_config
# from . import get_client
# async def some_service_function():
#     app_config = await get_config()
#     # Assuming 'translate' service uses 'openai' provider as per AppConfig
#     service_conf = app_config.services["translate"]
#     provider_conf = app_config.providers[service_conf.provider]
#     client = await get_client(service_conf.provider, provider_conf)
#     # Now use the client
