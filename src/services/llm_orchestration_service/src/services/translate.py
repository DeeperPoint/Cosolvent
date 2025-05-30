# services/translate.py
from ..config.store import get_config
from ..providers import get_client as get_llm_provider_client # Renamed to avoid confusion
from ..config.models import AppConfig, ServiceConfig, ProviderConfig
from ..core.logging import get_logger

logger = get_logger(__name__)

def render_prompt(service_name: str, text: str, template_version: str) -> str:
    """
    Renders a prompt for a given service and text.
    In a real scenario, this would use a more sophisticated template engine
    and load templates based on service_name and template_version.
    """
    # This is a very basic example. You'd likely have a template management system.
    if service_name == "translate":
        if template_version == "v1":
            return f"Translate the following text: \n{text}"
        else:
            return f"Please translate this: {text}"
    # Add other services and versions
    return text # Default fallback

async def translate(text: str, target_language: str, service_name: str = "translate") -> str:
    logger.info(f"Translation service called for text: '{text[:30]}...' to target language '{target_language}'")
    app_config: AppConfig = await get_config()
    
    # Determine service configuration
    if service_name not in app_config.services:
        logger.error(f"Service configuration for '{service_name}' not found.")
        raise ValueError(f"Service '{service_name}' is not configured.")
    
    service_cfg: ServiceConfig = app_config.services[service_name]

    if service_cfg.provider not in app_config.providers:
        logger.error(f"Provider configuration for '{service_cfg.provider}' not found for service '{service_name}'.")
        raise ValueError(f"Provider '{service_cfg.provider}' is not configured.")

    provider_cfg: ProviderConfig = app_config.providers[service_cfg.provider]
    
    client = await get_llm_provider_client(service_cfg.provider, provider_cfg)

    # Build prompt using configured templates or fallback
    opts = service_cfg.options or {}
    templates = opts.get("prompt_templates", {})
    default_key = opts.get("default_prompt_key")
    tpl = templates.get(default_key) if default_key else None
    if tpl:
        # Attempt to format with known variables; use empty string for missing ones
        try:
            prompt = tpl.format(source_language=opts.get("source_language", ""), target_language=target_language, text=text)
        except KeyError:
            prompt = tpl.format(text=text, target_language=target_language)
    else:
        prompt = render_prompt(
            service_name="translate",
            text=f"Translate to {target_language}: {text}",
            template_version=service_cfg.prompt_template_version
        )
    # Extract LLM parameters
    llm_params = opts.get("llm_params", {})
    translated_text = await client.call_model(prompt, **llm_params)
    logger.info(f"Translation successful for text: '{text[:30]}...'")
    return translated_text
