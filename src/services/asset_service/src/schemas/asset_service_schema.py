from pydantic import BaseModel, Field
from typing import Optional

class MetaData(BaseModel):
    """Additional metadata for an asset, e.g., generated description."""
    description: Optional[str] = Field(None, description="Description text for the asset")

class AssetCreate(BaseModel):
    user_id: str = Field(..., description="ID of the uploading user")
    filename: str = Field(..., description="Original file name")
    content_type: str = Field(..., description="MIME type of the file")
    file_type: str = Field(..., description="High-level file type (image, video, audio, text, pdf, docx)")

class AssetResponse(AssetCreate):
    id: str = Field(..., description="Database ID of the asset")
    url: str = Field(..., description="S3 URL to the stored file")
    meta_data: Optional[MetaData] = Field(
        default_factory=MetaData,
        description="Additional metadata (e.g., description)"
    )
