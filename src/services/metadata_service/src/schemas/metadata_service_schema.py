from pydantic import BaseModel

class AssetUploadedEvent(BaseModel):
    asset_id: str
    media_type: str

class MetadataResponse(BaseModel):
    asset_id: str
    description: str