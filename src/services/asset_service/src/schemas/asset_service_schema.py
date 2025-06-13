from pydantic import BaseModel, Field

class AssetCreate(BaseModel):
    user_id: str = Field(..., description="ID of the uploading user")
    filename: str = Field(..., description="Original file name")
    content_type: str = Field(..., description="MIME type of the file")
    file_type: str = Field(..., description="High-level file type (image, video, audio, text, pdf, docx)")

class AssetResponse(AssetCreate):
    id: str = Field(..., description="Database ID of the asset")
    url: str = Field(..., description="S3 URL to the stored file")
    description: str | None = Field(None, description="Text description of the asset")
    status: str | None = Field(None, description="Processing status of the asset (e.g., described)")

class AssetMetadataUpdate(BaseModel):
    description: str = Field(..., description="New description for the asset")
    status: str = Field(..., description="New processing status for the asset")
