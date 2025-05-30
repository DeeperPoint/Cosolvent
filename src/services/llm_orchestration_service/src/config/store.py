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
    # Acquire lock, update in-memory config, persist, then release lock
    await _config_lock.acquire()
    try:
        _config = new_config
        # persist_config writes file directly without lock
        await persist_config(_config, file_path)
        return _config
    finally:
        _config_lock.release()

async def persist_config(config_to_persist: AppConfig, file_path: Path = _config_file_path):
    """
    Persists the current configuration to a JSON file.
    Note: callers should hold _config_lock if necessary.
    """
    # Write file directly; avoid re-acquiring the config lock to prevent deadlocks
    with open(file_path, 'w') as f:
        json.dump(config_to_persist.model_dump(), f, indent=4)

async def patch_config(patch_data: dict, file_path: Path = _config_file_path) -> AppConfig:
    """
    Applies a partial update (PATCH) to the current AppConfig.
    Merges provided keys into existing config and persists the result.
    """
    global _config
    # Lock around in-memory update and persistence
    await _config_lock.acquire()
    try:
        if _config is None:
            await load_config(file_path)
        assert _config is not None, "Configuration not loaded"
        current_dict = _config.model_dump()
        # Merge patch_data into a copy
        merged = current_dict.copy()
        for key, value in patch_data.items():
            if key in ("providers", "services") and isinstance(value, dict):
                base_map = merged.get(key, {}).copy()
                for subkey, subpatch in value.items():
                    if isinstance(subpatch, dict) and subkey in base_map and isinstance(base_map[subkey], dict):
                        merged_sub = base_map[subkey].copy()
                        merged_sub.update(subpatch)
                        base_map[subkey] = merged_sub
                    else:
                        base_map[subkey] = subpatch
                merged[key] = base_map
            else:
                merged[key] = value
        _config = AppConfig(**merged)
        # persist_config writes file directly
        await persist_config(_config, file_path)
        return _config
    finally:
        _config_lock.release()

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
