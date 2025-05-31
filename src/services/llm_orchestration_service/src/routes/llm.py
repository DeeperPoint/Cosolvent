# routes/llm.py
from fastapi import APIRouter, HTTPException, Body, UploadFile, File, Depends
from pydantic import BaseModel
from typing import Dict, Any, List

from .. import services
from ..core.exceptions import LLMOrchestrationException, ConfigurationException
from ..core.logging import get_logger
from ..config.store import get_config, update_config, AppConfig # Import AppConfig for request/response model

router = APIRouter()
logger = get_logger(__name__)

# --- Request Models ---
class LLMCallRequest(BaseModel):
    text: str
    service_name: str = "direct_call"

class ProfileGenerationRequest(BaseModel):
    texts: List[str]
    service_name: str = "profile_generation"

class TranslateRequest(BaseModel): # Added back for the translate endpoint
    text: str
    target_language: str = "English"
    service_name: str = "translate"

# --- Response Models ---
class LLMServiceResponse(BaseModel):
    result: Any

class ProfileResponse(BaseModel):
    profile: Dict[str, Any]

# --- Endpoints ---

# Configuration Management Endpoints
@router.get("/config", response_model=AppConfig)
async def get_current_config():
    logger.info("Request to GET /config")
    try:
        config = await get_config()
        return config
    except Exception as e:
        logger.exception("Error retrieving configuration")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration.")

@router.put("/config", response_model=AppConfig)
async def update_app_config(new_config: AppConfig = Body(...)):
    logger.info("Request to PUT /config")
    try:
        # TODO: Implement more sophisticated validation of the incoming config if needed
        # For example, check if provider names in services exist in the providers section.
        updated_config = await update_config(new_config) # Pass the AppConfig object directly
        return updated_config
    except ConfigurationException as e:
        logger.error(f"Configuration error updating config: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error updating configuration")
        raise HTTPException(status_code=500, detail="Failed to update configuration.")

# Service Endpoints
@router.post("/call", response_model=LLMServiceResponse)
async def llm_call_endpoint(req: LLMCallRequest):
    logger.info(f"POST /call for service: {req.service_name}, text: '{req.text[:50]}...'")
    try:
        # TODO: Consider adding specific request validation if service_name implies certain text structure
        result = await services.direct_llm_call(text=req.text, service_name=req.service_name)
        return LLMServiceResponse(result=result)
    except ConfigurationException as e:
        logger.error(f"Configuration error in /call for service '{req.service_name}': {e}")
        raise HTTPException(status_code=400, detail=f"Configuration error: {e}")
    except LLMOrchestrationException as e:
        logger.error(f"LLM Orchestration error in /call for service '{req.service_name}': {e}")
        raise HTTPException(status_code=500, detail=f"LLM service error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in /call for service '{req.service_name}'")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@router.post("/translate", response_model=LLMServiceResponse)
async def translate_endpoint(req: TranslateRequest):
    logger.info(f"POST /translate for service: {req.service_name}, target: {req.target_language}, text: '{req.text[:50]}...'")
    try:
        result = await services.translate(text=req.text, target_language=req.target_language, service_name=req.service_name)
        return LLMServiceResponse(result=result)
    except ConfigurationException as e:
        logger.error(f"Configuration error in /translate for service '{req.service_name}': {e}")
        raise HTTPException(status_code=400, detail=f"Configuration error: {e}")
    except LLMOrchestrationException as e:
        logger.error(f"LLM Orchestration error in /translate for service '{req.service_name}': {e}")
        raise HTTPException(status_code=500, detail=f"LLM service error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in /translate for service '{req.service_name}'")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@router.post("/metadata", response_model=LLMServiceResponse)
async def metadata_extraction_endpoint(service_name: str = "metadata_extraction", file: UploadFile = File(...)):
    logger.info(f"POST /metadata for service: {service_name}, file: {file.filename}")
    if not file.filename:
        # TODO: Consider generating a default filename if none is provided by the client, or reject earlier.
        logger.warning("File name not provided in metadata_extraction_endpoint.")
        raise HTTPException(status_code=400, detail="File name is required.")
    try:
        raw = await services.extract_textual_metadata_from_file(file=file, service_name=service_name)
        # wrap raw metadata string into an envelope with description field
        return LLMServiceResponse(result={"description": raw})
    except ConfigurationException as e:
        logger.error(f"Configuration error in /metadata for service '{service_name}': {e}")
        raise HTTPException(status_code=400, detail=f"Configuration error: {e}")
    except LLMOrchestrationException as e:
        logger.error(f"LLM Orchestration error in /metadata for service '{service_name}': {e}")
        raise HTTPException(status_code=500, detail=f"LLM service error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in /metadata for service '{service_name}', file '{file.filename}'")
        raise HTTPException(status_code=500, detail="An unexpected error occurred processing file.")

@router.post("/generate-profile", response_model=ProfileResponse)
async def generate_profile_endpoint(req: ProfileGenerationRequest):
    logger.info(f"POST /generate-profile for service: {req.service_name} with {len(req.texts)} texts.")
    try:
        profile_dict = await services.generate_structured_profile(texts=req.texts, service_name=req.service_name)
        
        # The service now raises exceptions for errors, so direct error check in dict might be less common
        # unless specific partial errors are returned by design.
        if isinstance(profile_dict, dict) and "error" in profile_dict:
            logger.error(f"Profile generation service '{req.service_name}' returned an error structure: {profile_dict.get('details')}")
            # TODO: Standardize error responses from services. If an error occurs that isn't an exception,
            # this path might still be hit. Consider if services should always raise exceptions on failure.
            raise HTTPException(status_code=422, detail=profile_dict) 
        
        return ProfileResponse(profile=profile_dict)
    except ConfigurationException as e:
        logger.error(f"Configuration error in /generate-profile for service '{req.service_name}': {e}")
        raise HTTPException(status_code=400, detail=f"Configuration error: {e}")
    except LLMOrchestrationException as e:
        logger.error(f"LLM Orchestration error in /generate-profile for service '{req.service_name}': {e}")
        # TODO: Differentiate between client errors (4xx) and server errors (5xx) from LLMOrchestrationException if possible
        raise HTTPException(status_code=500, detail=f"LLM service error: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in /generate-profile for service '{req.service_name}'")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

# Ensure all services from __init__.py have corresponding endpoints if they are user-facing.
# Current services: direct_llm_call, extract_textual_metadata_from_file, generate_structured_profile, translate
