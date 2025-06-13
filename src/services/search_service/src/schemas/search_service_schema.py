from pydantic import BaseModel

class AssetReadyForIndexing(BaseModel):
    asset_id: str
    user_id: str
    description: str
