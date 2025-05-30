# routes/config.py
from fastapi import APIRouter, HTTPException
from ..config.models import AppConfig # Use .. to go up one level to src, then to config
from ..config import store as config_store # Use .. to go up one level to src, then to config
from ..core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Helper to mask sensitive api_key values in providers
def _mask_providers_api_keys(cfg: AppConfig) -> AppConfig:
    """Return AppConfig with provider api_key partially masked."""
    from typing import Optional

    def _mask_key(key: Optional[str]) -> Optional[str]:
        if not key:
            return None
        n = len(key)
        if n <= 8:
            return '*' * n
        # show first 4 and last 4, mask middle
        return key[:4] + '*' * (n - 8) + key[-4:]

    masked = {}
    for name, pc in cfg.providers.items():
        masked[name] = pc.copy(update={"api_key": _mask_key(pc.api_key)})
    return cfg.copy(update={"providers": masked})

@router.get("", response_model=AppConfig)
async def read_config_endpoint(): # Renamed to avoid conflict with imported `config` module
    """Returns the full AppConfig tree.
    Credentials in ProviderConfig should ideally be masked if sensitive.
    This example does not implement masking.
    """
    logger.info("GET /config endpoint called")
    try:
        current_config = await config_store.get_all()
        return _mask_providers_api_keys(current_config)
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
        return _mask_providers_api_keys(updated_config)
    except Exception as e:
        logger.exception("Error updating configuration")
        raise HTTPException(status_code=500, detail=f"Error updating configuration: {e}")

@router.patch("", response_model=AppConfig)
async def patch_config_endpoint(patch_data: dict):
    """
    Partially update the AppConfig by merging provided fields.
    """
    logger.info("PATCH /config endpoint called")
    try:
        updated_config = await config_store.patch_config(patch_data)
        logger.info("Configuration patched successfully.")
        return _mask_providers_api_keys(updated_config)
    except Exception as e:
        logger.exception("Error patching configuration")
        raise HTTPException(status_code=500, detail=f"Error patching configuration: {e}")
