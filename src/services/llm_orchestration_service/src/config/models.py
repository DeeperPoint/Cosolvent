from pydantic import BaseModel, Field
from typing import Dict, Optional, Any

class ProviderConfig(BaseModel):
    name: str
    api_key: Optional[str] = None # Made optional, client should check
    endpoint: Optional[str] = None # Made optional
    model: str
    options: Optional[Dict[str, Any]] = None # Added for provider-specific options

class ServiceConfig(BaseModel):
    provider: str                       # key into providers dict
    prompt_template_version: str
    cache_enabled: bool = False
    profile_schema: Optional[Dict[str, Any]] = None # Added for profile generation
    options: Optional[Dict[str, Any]] = None # Already existed, good

class AppConfig(BaseModel):
    providers: Dict[str, ProviderConfig]
    services: Dict[str, ServiceConfig]  # e.g. “translate”, “search”, etc.
