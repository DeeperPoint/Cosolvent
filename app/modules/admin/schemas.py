from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ApprovalAction(BaseModel):
    feedback: str | None = None


class UserRoleUpdate(BaseModel):
    role: Literal["user", "admin"]


class UserStatusUpdate(BaseModel):
    is_active: bool


class ProfileStatusUpdate(BaseModel):
    status: Literal["active", "suspended", "pending"]


class FAQCreate(BaseModel):
    question: str
    answer: str
    category: str | None = None
    sort_order: int = 0


class FAQUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    category: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
