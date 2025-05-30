from pydantic import BaseModel
from typing import Any

class ProxyResponse(BaseModel):
    """
    Envelope model for proxied responses.
    """
    status_code: int
    content: Any