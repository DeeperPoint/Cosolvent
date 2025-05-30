# providers/openai_client.py
import openai
from tenacity import retry, stop_after_attempt, wait_exponential
from .base import LLMClient
from ..config.models import ProviderConfig
from ..core.exceptions import LLMApiException, ConfigurationException
from ..core.logging import get_logger
import io
import base64
from typing import List, Dict, Any, Union # Added Union for message content

logger = get_logger(__name__)

# Define a type for the message content part
MessageContentPart = Union[
    Dict[str, str], # For text content: {"type": "text", "text": "..."}
    Dict[str, Any]  # For image_url content: {"type": "image_url", "image_url": {"url": "...", "detail": "..."}}
]

class OpenAIClient(LLMClient):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.client = openai.AsyncOpenAI(api_key=self.config.api_key, base_url=self.config.endpoint if self.config.endpoint else None)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def call_model(self, prompt: str, **kwargs) -> str:
        logger.info(f"Calling OpenAI model '{self.config.model}' for provider '{self.config.name}'")
        
        image_bytes = kwargs.pop("image_bytes", None)
        
        # Correctly typed messages list
        # The top-level message content is a list of these parts.
        message_parts: List[MessageContentPart] = [] 
        message_parts.append({"type": "text", "text": prompt})

        if image_bytes and self.config.model in ["gpt-4-vision-preview", "gpt-4o", "gpt-4-turbo"]:
            logger.info(f"Processing image for model {self.config.model}")
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            message_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}", # Assuming JPEG
                    # "detail": "high" # Optional: can be 'low', 'high', or 'auto'
                }
            })
        elif image_bytes:
            logger.warning(f"Model {self.config.model} does not support images. Image data will be ignored.")

        # Construct the final messages structure for the API
        api_messages = [
            {
                "role": "user",
                "content": message_parts # Content is a list of parts
            }
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=api_messages, # type: ignore # Trusting the structure matches ChatCompletionMessageParam
                **kwargs
            )
            content = response.choices[0].message.content
            if content is None:
                raise LLMApiException(self.config.name, Exception("No content in response"))
            logger.info(f"Successfully received response from OpenAI model '{self.config.model}'")
            return content
        except Exception as e:
            logger.error(f"Error calling OpenAI model '{self.config.model}': {e}")
            raise LLMApiException(provider_name=self.config.name, original_exception=e)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def call_stt_model(self, audio_bytes: bytes, filename: str = "audio_file.mp3", **kwargs) -> str:
        logger.info(f"Calling OpenAI STT model '{self.config.model}' (likely Whisper) for provider '{self.config.name}'")
        if not self.config.model or "whisper" not in self.config.model.lower():
            msg = f"Provider {self.config.name} with model {self.config.model} is not configured for STT (Whisper)."
            logger.error(msg)
            raise ConfigurationException(msg)
        try:
            audio_file_like = io.BytesIO(audio_bytes)
            
            # Ensure filename has an extension if not provided, helps Whisper with format detection.
            # Defaulting to mp3 as an example, but it's better if the caller provides an accurate filename.
            _filename = filename if '.' in filename else f"{filename}.mp3"

            transcription_response = await self.client.audio.transcriptions.create(
                model=self.config.model,
                file=(_filename, audio_file_like, kwargs.get("mime_type", "application/octet-stream")),
                response_format=kwargs.get("response_format", "text")
            )
            logger.info(f"Successfully received STT response from OpenAI model '{self.config.model}'")
            
            # Handle different response formats from OpenAI STT
            if isinstance(transcription_response, str): # For response_format='text'
                return transcription_response
            # For response_format='json' or 'verbose_json', it's an object with a 'text' attribute
            elif hasattr(transcription_response, 'text'):
                return transcription_response.text # type: ignore
            else:
                # Fallback if the response structure is unexpected
                logger.error(f"Unexpected STT response format: {type(transcription_response)}. Content: {str(transcription_response)[:200]}")
                raise LLMApiException(provider_name=self.config.name, original_exception=Exception("Unexpected STT response format from OpenAI."))

        except Exception as e:
            logger.error(f"Error calling OpenAI STT model '{self.config.model}': {e}")
            raise LLMApiException(provider_name=self.config.name, original_exception=e)
