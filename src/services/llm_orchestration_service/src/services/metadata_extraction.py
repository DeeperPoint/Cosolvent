# services/metadata_extraction.py
from ..config.store import get_config
from ..providers import get_client as get_llm_provider_client
from ..config.models import AppConfig, ServiceConfig, ProviderConfig
from ..core.logging import get_logger
from fastapi import UploadFile
import mimetypes
import asyncio

logger = get_logger(__name__)

# Placeholder for a function that would convert image to text (e.g., using an OCR or image-to-text model)
async def image_to_text(file_content: bytes, provider_config: ProviderConfig, llm_client) -> str:
    logger.info("Attempting to convert image to text (placeholder).")
    # In a real implementation, you would use a specific model/service for this.
    # This might involve another call to an LLM or a specialized vision service.
    # For now, this is a placeholder.
    # Example: return await llm_client.call_model(prompt="Describe this image.", image_bytes=file_content)
    # This depends heavily on the capabilities of the chosen llm_client and provider_config.
    if "openai" in provider_config.name.lower() and provider_config.model in ["gpt-4-vision-preview", "gpt-4o"]:
        # This is a conceptual example; actual OpenAI API call for vision would be different.
        # You'd typically send the image data (e.g., base64 encoded) as part of the message content.
        # The `call_model` would need to be adapted to handle multimodal inputs.
        # For now, we simulate this by returning a descriptive string.
        logger.warning("Image-to-text for OpenAI vision models is conceptual here. Actual implementation needed.")
        return "[Placeholder: Textual description of an image that was processed by a vision model]"
    return "[Placeholder image content as text: a cat sitting on a mat]"

# Placeholder for a function that would convert audio/video to text (Speech-to-Text)
async def speech_to_text(file_content: bytes, provider_config: ProviderConfig, llm_client) -> str:
    logger.info("Attempting to convert speech to text (placeholder).")
    # Use a specific STT model/service (e.g., OpenAI Whisper, Google Speech-to-Text)
    # Example: return await llm_client.call_stt_model(audio_bytes=file_content)
    # This also depends on the llm_client supporting such calls or using a separate client.
    if "openai" in provider_config.name.lower(): # Assuming Whisper access via OpenAI client or similar
        logger.warning("Speech-to-text for OpenAI (e.g., Whisper) is conceptual. Actual implementation needed.")
        return "[Placeholder: Transcribed text from an audio/video file using a speech-to-text model like Whisper]"
    return "[Placeholder audio content as text: Hello world, this is a test.]"

async def extract_textual_metadata_from_file(file: UploadFile, service_name: str = "metadata_extraction") -> str:
    logger.info(f"Metadata extraction service called for file: {file.filename}, type: {file.content_type}")
    app_config: AppConfig = await get_config()

    if service_name not in app_config.services:
        logger.error(f"Service configuration for '{service_name}' not found.")
        raise ValueError(f"Service '{service_name}' is not configured.")

    service_cfg: ServiceConfig = app_config.services[service_name]

    if service_cfg.provider not in app_config.providers:
        logger.error(f"Provider configuration for '{service_cfg.provider}' not found for service '{service_name}'.")
        raise ValueError(f"Provider '{service_cfg.provider}' is not configured.")

    provider_cfg: ProviderConfig = app_config.providers[service_cfg.provider]
    # Retrieve processing-specific configurations
    opts = service_cfg.options or {}
    llm_client = None  # Placeholder, will be set per processing type

    file_content = await file.read()
    text_content_for_llm = ""

    mime_type = file.content_type
    if not mime_type and file.filename:
        mime_type, _ = mimetypes.guess_type(file.filename)

    if mime_type:
        if mime_type.startswith("image/"):
            logger.info(f"Processing image file: {file.filename}")
            # Use image_processing config to convert image to text via VLM provider
            proc_cfg = opts.get("image_processing", {})
            vlm_provider = proc_cfg.get("vlm_provider")
            vlm_template = proc_cfg.get("vlm_prompt_template", "")
            vlm_params = proc_cfg.get("llm_params", {})
            if vlm_provider and vlm_provider in app_config.providers:
                vlm_provider_cfg = app_config.providers[vlm_provider]
                vlm_client = await get_llm_provider_client(vlm_provider, vlm_provider_cfg)
                # Render VLM prompt
                try:
                    vlm_prompt = vlm_template.format(file_name=file.filename)
                except Exception:
                    vlm_prompt = vlm_template
                text_content_for_llm = await vlm_client.call_model(vlm_prompt, **vlm_params)
            else:
                text_content_for_llm = await image_to_text(file_content, provider_cfg, None)
        elif mime_type.startswith("audio/") or mime_type.startswith("video/"):
            logger.info(f"Processing audio/video file: {file.filename}")
            # Use audio_processing config for STT
            proc_cfg = opts.get("audio_processing", {})
            stt_provider = proc_cfg.get("stt_provider")
            stt_options = proc_cfg.get("stt_options", {})
            if stt_provider and stt_provider in app_config.providers:
                stt_provider_cfg = app_config.providers[stt_provider]
                stt_client = await get_llm_provider_client(stt_provider, stt_provider_cfg)
                # Placeholder: call STT model via call_stt_model if supported
                try:
                    text_content_for_llm = await stt_client.call_stt_model(file_content, **stt_options)
                except AttributeError:
                    text_content_for_llm = await speech_to_text(file_content, provider_cfg, None)
            else:
                text_content_for_llm = await speech_to_text(file_content, provider_cfg, None)
        elif mime_type.startswith("text/") or mime_type == "application/json" or mime_type == "application/xml":
            logger.info(f"Processing text-based file: {file.filename}")
            try:
                text_content_for_llm = file_content.decode('utf-8')
            except UnicodeDecodeError:
                logger.warning(f"Could not decode file {file.filename} as UTF-8, trying latin-1")
                text_content_for_llm = file_content.decode('latin-1', errors='ignore')
        else:
            logger.warning(f"Unsupported file type: {mime_type} for file {file.filename}. Attempting generic text extraction.")
            # Fallback for unknown but potentially text-based types or to inform the LLM about the file type
            text_content_for_llm = f"[Content from an unsupported file type: {mime_type}. Raw content might follow, or this is a placeholder.]"
            # Depending on policy, you might raise an error here or try to process as raw bytes if the LLM can handle it.

    else:
        logger.warning(f"Could not determine MIME type for file: {file.filename}. No processing will occur.")
        raise ValueError(f"Could not determine MIME type for file: {file.filename}. Cannot process.")

    if not text_content_for_llm:
        logger.warning(f"No text content extracted from file {file.filename} to send to LLM.")
        return "[No textual content could be extracted or generated from the provided file for metadata analysis.]"

    # Use nested metadata prompts based on processing type
    proc_key = None
    if mime_type.startswith("image/"):
        proc_key = "image_processing"
    elif mime_type.startswith("audio/") or mime_type.startswith("video/"):
        proc_key = "audio_processing"
    else:
        proc_key = "document_processing"
    proc_cfg = opts.get(proc_key, {})
    meta_provider = proc_cfg.get("metadata_llm_provider") or proc_cfg.get("llm_provider")
    meta_template = proc_cfg.get("metadata_llm_prompt_template", "{text}")
    meta_params = proc_cfg.get("llm_params", {})
    if meta_provider and meta_provider in app_config.providers:
        meta_provider_cfg = app_config.providers[meta_provider]
        meta_client = await get_llm_provider_client(meta_provider, meta_provider_cfg)
        # Determine placeholder key for formatting
        format_args = {}
        if "vlm_output" in meta_template:
            format_args["vlm_output"] = text_content_for_llm
        elif "stt_output" in meta_template:
            format_args["stt_output"] = text_content_for_llm
        elif "document_text" in meta_template:
            format_args["document_text"] = text_content_for_llm
        else:
            format_args["text"] = text_content_for_llm
        try:
            prompt = meta_template.format(**format_args)
        except Exception:
            prompt = text_content_for_llm
        extracted_metadata = await meta_client.call_model(prompt, **meta_params)
        logger.info(f"Metadata extraction from file {file.filename} successful.")
        return extracted_metadata
    else:
        logger.warning(f"No metadata LLM provider configured for {proc_key}. Returning raw text.")
        return text_content_for_llm
