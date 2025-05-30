# routes/__init__.py
from fastapi import APIRouter

from . import llm
from . import config

router = APIRouter()

router.include_router(llm.router, prefix="/llm", tags=["LLM Services"])
router.include_router(config.router, prefix="/config", tags=["Configuration"])

# This __init__.py aggregates all routers for the main app.
