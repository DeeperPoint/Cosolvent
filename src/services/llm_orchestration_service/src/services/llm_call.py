# services/llm_call.py
from ..config.store import get_config
from ..providers import get_client as get_llm_provider_client
from ..config.models import AppConfig, ServiceConfig, ProviderConfig
from ..core.logging import get_logger

logger = get_logger(__name__)

async def direct_llm_call(text: str, service_name: str = "direct_call") -> str:
    logger.info(f"Direct LLM call service invoked for service: {service_name} with text: '{text[:50]}...'")
    app_config: AppConfig = await get_config()

    if service_name not in app_config.services:
        logger.error(f"Service configuration for '{service_name}' not found.")
        # Fallback to a default provider if a specific service config isn't found for direct_call
        # This requires a "default_provider" to be configured in app_config.providers
        # Or, you might want to raise an error if explicit config is always required.
        # For this example, let's assume a default provider can be used if service_name is not in app_config.services
        # and we will try to use the first available provider or a specifically named default.
        # This part needs careful consideration based on desired behavior.

        # Simplified: let's assume 'direct_call' service must be configured
        raise ValueError(f"Service '{service_name}' is not configured. Please add it to config.json.")

    service_cfg: ServiceConfig = app_config.services[service_name]

    if service_cfg.provider not in app_config.providers:
        logger.error(f"Provider configuration for '{service_cfg.provider}' not found for service '{service_name}'.")
        raise ValueError(f"Provider '{service_cfg.provider}' is not configured.")

    provider_cfg: ProviderConfig = app_config.providers[service_cfg.provider]
    client = await get_llm_provider_client(service_cfg.provider, provider_cfg)

    # For a direct call, apply prompt template if provided, otherwise use the raw text
    opts = service_cfg.options or {}
    prompt_template = opts.get("prompt_template")
    if prompt_template:
        prompt = prompt_template.format(text=text)
    else:
        prompt = text

    # Extract LLM parameters from service options
    llm_params = opts.get("llm_params", {})
    # TODO: Implement caching if service_cfg.cache_enabled is True
    response_text = await client.call_model(prompt, **llm_params)
    logger.info(f"Direct LLM call successful for service: {service_name}.")
    return response_text
