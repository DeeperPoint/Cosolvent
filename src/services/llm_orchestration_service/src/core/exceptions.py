# core/exceptions.py
class LLMOrchestrationException(Exception):
    """Base exception for the LLM Orchestration service."""
    pass

class ProviderNotFoundException(LLMOrchestrationException):
    """Raised when a specified LLM provider is not found."""
    def __init__(self, provider_name: str):
        super().__init__(f"Provider '{provider_name}' not found.")
        self.provider_name = provider_name

class LLMApiException(LLMOrchestrationException):
    """Raised when an LLM provider API call fails."""
    def __init__(self, provider_name: str, original_exception: Exception):
        super().__init__(f"API call to provider '{provider_name}' failed: {original_exception}")
        self.provider_name = provider_name
        self.original_exception = original_exception

class ConfigurationException(LLMOrchestrationException):
    """Raised for configuration-related errors."""
    pass
