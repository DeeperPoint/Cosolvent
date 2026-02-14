from __future__ import annotations

from pydantic import BaseModel


class ApprovalAction(BaseModel):
    feedback: str | None = None
