# config/store.py
import json
import asyncio
from typing import Optional
from pathlib import Path
from .models import AppConfig

# Placeholder for the actual configuration data
_config: Optional[AppConfig] = None
_config_lock = asyncio.Lock()
_config_file_path = Path(__file__).parent.parent.parent / "config.json" # Example path, adjust as needed

async def load_config(file_path: Path = _config_file_path) -> AppConfig:
    """
    Loads default config at startup (from JSON or env).
    For simplicity, this example loads from a JSON file.
    """
    global _config
    async with _config_lock:
        if _config is None:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    _config = AppConfig(**data)
            else:
                # Create a default/empty config if file doesn't exist
                # This should be replaced with actual default configuration logic
                _config = AppConfig(providers={}, services={})
                # Persist this default config
                await persist_config(_config, file_path)

        if _config is None: # Should not happen if default is created
            raise ValueError("Configuration could not be loaded.")
        return _config

async def get_config() -> AppConfig:
    """
    Provides an async-safe getter for the current AppConfig.
    """
    async with _config_lock:
        if _config is None:
            await load_config() # Ensure config is loaded
        if _config is None: # Still None after attempt to load
             raise RuntimeError("Configuration has not been loaded.")
        return _config

async def update_config(new_config: AppConfig, file_path: Path = _config_file_path) -> AppConfig:
    """
    Provides an async-safe setter for AppConfig.
    On update, optionally persists back to file.
    """
    global _config
    async with _config_lock:
        _config = new_config
        await persist_config(_config, file_path)
        return _config

async def persist_config(config_to_persist: AppConfig, file_path: Path = _config_file_path):
    """
    Persists the current configuration to a JSON file.
    """
    async with _config_lock: # Ensure thread-safety for file writing if called directly
        with open(file_path, 'w') as f:
            json.dump(config_to_persist.model_dump(), f, indent=4)

# Expose specific parts of the config if needed, e.g.:
# async def get_service_config(service_name: str) -> ServiceConfig:
#     app_cfg = await get_config()
#     return app_cfg.services[service_name]

# async def get_provider_config(provider_name: str) -> ProviderConfig:
#     app_cfg = await get_config()
#     return app_cfg.providers[provider_name]

# For routes/config.py
async def get_all() -> AppConfig:
    return await get_config()

async def update(new: AppConfig) -> AppConfig:
    return await update_config(new)
