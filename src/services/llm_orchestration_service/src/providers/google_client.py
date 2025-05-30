# providers/google_client.py
import asyncio
import os
from typing import List, Dict, Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import google.generativeai as genai
# Correctly import types from the SDK
from google.generativeai.types import GenerationConfig, SafetySettingDict
from google.generativeai.types.safety_types import HarmCategory, HarmBlockThreshold # More specific import
from google.api_core.exceptions import GoogleAPIError, RetryError, ServiceUnavailable, DeadlineExceeded, InvalidArgument

from .base import LLMClient
from ..config.models import ProviderConfig
from ..core.exceptions import LLMApiException, ConfigurationException
from ..core.logging import get_logger

logger = get_logger(__name__)

RETRYABLE_GOOGLE_EXCEPTIONS = (
    RetryError,
    ServiceUnavailable,
    DeadlineExceeded,
)

# Default retry parameters, can be overridden by config.options in the future if needed
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_MULTIPLIER = 1
DEFAULT_RETRY_MIN_WAIT = 2
DEFAULT_RETRY_MAX_WAIT = 10

class GoogleClient(LLMClient):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        
        api_key_to_configure = self.config.api_key or os.getenv("GOOGLE_API_KEY")
        
        if not api_key_to_configure:
            logger.warning(
                f"Google API key not explicitly set in config for {self.config.name} "
                "and GOOGLE_API_KEY env var not found. "
                "Relying on default credentials if available, or initialization might fail."
            )
        
        if not self.config.model:
            raise ConfigurationException(f"Model not configured for Google provider: {self.config.name}")
        
        try:
            # Configure the API key if provided.
            # The SDK might also pick it up from GOOGLE_API_KEY environment variable automatically.
            if api_key_to_configure:
                genai.configure(api_key=api_key_to_configure)
            
            # Initialize the GenerativeModel
            self.model = genai.GenerativeModel(self.config.model)
            logger.info(f"Google LLM Client initialized for model: {self.config.model} (Provider: {self.config.name})")

        except AttributeError as ae:
            logger.error(
                f"Failed to initialize Google Client due to SDK attribute error: {ae}. "
                "This often means `genai.configure` or `genai.GenerativeModel` was not found. "
                "Ensure 'google-generativeai' library is correctly installed and the version is compatible. "
                f"Provider: '{self.config.name}', Model: '{self.config.model}'"
            )
            raise ConfigurationException(
                f"Google SDK attribute error for provider '{self.config.name}': {ae}. "
                "Check library installation and version."
            )
        except Exception as e:
            logger.error(f"Failed to initialize Google Client for model {self.config.model}: {e}")
            raise ConfigurationException(f"Google SDK initialization error for provider '{self.config.name}': {e}")

    @retry(
        stop=stop_after_attempt(DEFAULT_MAX_RETRIES),
        wait=wait_exponential(
            multiplier=DEFAULT_RETRY_MULTIPLIER,
            min=DEFAULT_RETRY_MIN_WAIT,
            max=DEFAULT_RETRY_MAX_WAIT
        ),
        retry=retry_if_exception_type(RETRYABLE_GOOGLE_EXCEPTIONS)
    )
    async def call_model(self, prompt: str, **kwargs) -> str:
        logger.info(f"Calling Google model '{self.config.model}' (Provider: '{self.config.name}') with prompt: '{prompt[:100]}...'")

        # Get generation_config and safety_settings from kwargs or provider options
        provider_opts = self.config.options or {}
        generation_config_dict = kwargs.get("generation_config", provider_opts.get("generation_config", {}))
        safety_settings_input = kwargs.get("safety_settings", provider_opts.get("safety_settings", []))

        gen_config_instance: GenerationConfig | None = None
        if isinstance(generation_config_dict, dict) and generation_config_dict:
            try:
                gen_config_instance = GenerationConfig(**generation_config_dict)
            except TypeError as te:
                logger.warning(
                    f"Invalid parameters in generation_config for Google model '{self.config.model}': {te}. "
                    "Using SDK defaults."
                )
        elif isinstance(generation_config_dict, GenerationConfig): # Already a GenerationConfig object
            gen_config_instance = generation_config_dict


        processed_safety_settings: List[Any] = [] # Use List[Any] to bypass linter confusion
        if isinstance(safety_settings_input, list):
            for setting_item in safety_settings_input:
                if isinstance(setting_item, dict): # Each item should be a dict
                    try:
                        category_str = setting_item.get("category")
                        threshold_str = setting_item.get("threshold")
                        if category_str and threshold_str:
                            # Convert string keys to Enum members
                            category = HarmCategory[category_str.upper()]
                            threshold = HarmBlockThreshold[threshold_str.upper()]
                            # The SDK expects a list of dictionaries with HarmCategory and HarmBlockThreshold enums
                            processed_safety_settings.append({"category": category, "threshold": threshold})
                        else:
                            logger.warning(
                                f"Skipping safety setting for '{self.config.model}' due to missing "
                                f"'category' or 'threshold': {setting_item}"
                            )
                    except KeyError as ke:
                        logger.warning(
                            f"Invalid HarmCategory/Threshold string in safety_settings for '{self.config.model}': {ke}. "
                            f"Setting: {setting_item}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Error processing safety_setting '{setting_item}' for '{self.config.model}': {e}. Skipping."
                        )
                # If it's already in the correct format (e.g. from a more typed source), one might pass it directly
                # For now, we assume it's a list of dicts from JSON config.

        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=gen_config_instance,
                safety_settings=processed_safety_settings if processed_safety_settings else None,
            )

            text_response = ""
            try:
                # response.text is a convenience accessor.
                # It might raise ValueError if the content isn't simple text (e.g., function call)
                # or if the prompt was blocked.
                text_response = response.text
            except ValueError as ve:
                logger.warning(
                    f"ValueError accessing .text for model '{self.config.model}' (prompt: '{prompt[:50]}...'): {ve}. "
                    "This can happen if the response is not simple text (e.g. function call) or was blocked. "
                    "Checking parts and candidates."
                )
                # Fall through to check parts/candidates
            except Exception as e: # Catch other errors from .text (e.g. if response is blocked)
                logger.error(
                    f"Error accessing .text for model '{self.config.model}' (prompt: '{prompt[:50]}...'): {e}. "
                    "Checking for block reason."
                )
                 # Fall through to check block reason and parts/candidates

            # If .text was empty or failed, and not due to blocking, try to construct from parts/candidates
            if not text_response:
                if response.parts:
                    for part in response.parts:
                        if hasattr(part, 'text') and part.text:
                            text_response += part.text
                elif response.candidates: # Check candidates if parts are also empty or non-textual
                    for candidate in response.candidates:
                        if hasattr(candidate, 'content') and candidate.content and \
                           hasattr(candidate.content, 'parts') and candidate.content.parts:
                            for part in candidate.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    text_response += part.text
                            if text_response: # Found text in this candidate
                                break
            
            # Final check for blocking, especially if text_response is still empty
            if not text_response and response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason_msg = (
                    f"Prompt blocked by Google API for model '{self.config.model}'. "
                    f"Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}"
                )
                logger.error(block_reason_msg)
                raise LLMApiException(provider_name=self.config.name, original_exception=Exception(block_reason_msg))

            if not text_response:
                logger.warning(f"Google model '{self.config.model}' response was empty or non-textual after all checks.")
            
            logger.info(f"Successfully received response from Google model '{self.config.model}'. Length: {len(text_response)}")
            return text_response

        except InvalidArgument as iae:
            logger.error(f"Invalid argument calling Google model '{self.config.model}': {iae}")
            # This could be due to malformed safety_settings or generation_config
            raise LLMApiException(provider_name=self.config.name, original_exception=iae)
        except (GoogleAPIError, RetryError, ServiceUnavailable, DeadlineExceeded) as e:
            logger.error(f"Google API error calling model '{self.config.model}': {type(e).__name__} - {e}")
            raise # Re-raise for tenacity to handle retry
        except Exception as e:
            logger.error(f"Unexpected error calling Google model '{self.config.model}': {type(e).__name__} - {e}")
            raise LLMApiException(provider_name=self.config.name, original_exception=e)

# Ensure you install the necessary package: pip install google-generativeai
# And that the API key is correctly set in the environment or config.
