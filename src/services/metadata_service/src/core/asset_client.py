import httpx
from ..schemas.asset import AssetUpdatePayload
from .config import settings

async def update_metadata(payload: AssetUpdatePayload) -> None:
    url = f"{settings.asset_service_url}/assets/{payload.asset_id}/metadata"
    async with httpx.AsyncClient() as client:
        resp = await client.patch(url, json=payload.dict())
        resp.raise_for_status()