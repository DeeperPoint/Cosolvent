from pydantic import BaseModel, UUID4
from datetime import datetime

class AssetUpdatePayload(BaseModel):
    asset_id: UUID4
    description: str
    status: str = "described"

class AssetReadyForIndexing(BaseModel):
    asset_id: UUID4
    user_id: UUID4
    description: str
    timestamp: datetime = datetime.utcnow()