# routes/config.py
from fastapi import APIRouter, HTTPException
from ..config.models import AppConfig # Use .. to go up one level to src, then to config
from ..config import store as config_store # Use .. to go up one level to src, then to config
from ..core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.get("", response_model=AppConfig)
async def read_config_endpoint(): # Renamed to avoid conflict with imported `config` module
    """Returns the full AppConfig tree.
    Credentials in ProviderConfig should ideally be masked if sensitive.
    This example does not implement masking.
    """
    logger.info("GET /config endpoint called")
    try:
        current_config = await config_store.get_all()
        # Add masking for sensitive fields like api_key before returning
        # For example:
        # masked_providers = {}
        # for name, pc in current_config.providers.items():
        #     masked_pc = pc.copy(update={"api_key": "********" if pc.api_key else None})
        #     masked_providers[name] = masked_pc
        # return current_config.copy(update={"providers": masked_providers})
        return current_config
    except Exception as e:
        logger.exception("Error reading configuration")
        raise HTTPException(status_code=500, detail=f"Error reading configuration: {e}")

@router.put("", response_model=AppConfig)
async def update_config_endpoint(new_config: AppConfig): # Renamed to avoid conflict
    """
    Accepts a new AppConfig document, enabling on-the-fly updates.
    """
    logger.info("PUT /config endpoint called")
    try:
        updated_config = await config_store.update(new_config)
        logger.info("Configuration updated successfully.")
        return updated_config
    except Exception as e:
        logger.exception("Error updating configuration")
        raise HTTPException(status_code=500, detail=f"Error updating configuration: {e}")
