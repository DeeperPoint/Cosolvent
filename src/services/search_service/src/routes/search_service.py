from fastapi import APIRouter

router = APIRouter()

@router.get("/health", tags=["Search"])
async def health():
    return {"status": "ok"}
