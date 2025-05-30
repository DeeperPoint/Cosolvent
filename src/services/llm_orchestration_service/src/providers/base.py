# providers/base.py
from abc import ABC, abstractmethod
from ..config.models import ProviderConfig
from typing import Any # Added for **kwargs in call_stt_model

class LLMClient(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    async def call_model(self, prompt: str, **kwargs: Any) -> str:
        """Makes a call to the LLM and returns the response as a string."""
        ...

    # Add an optional call_stt_model to the base class
    # Implementations can override this if they support STT
    async def call_stt_model(self, audio_bytes: bytes, filename: str, **kwargs: Any) -> str:
        """Makes a call to an STT model and returns the transcribed text."""
        raise NotImplementedError(
            f"'{self.__class__.__name__}' does not support STT directly via call_stt_model. "
            f"Provider: {self.config.name}, Model: {self.config.model}"
        )
