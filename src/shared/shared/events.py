from enum import Enum
from datetime import datetime
from typing import Union, Annotated

from pydantic import BaseModel, Field


class AssetType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    DOCUMENT = "document"  # covers PDF, DOCX, etc.


class ImageMetadata(BaseModel):
    width: int
    height: int
    format: str  # e.g., "png", "jpg"


class VideoMetadata(BaseModel):
    duration_seconds: float
    codec: str
    resolution: str  # e.g., "1920x1080"


class AudioMetadata(BaseModel):
    duration_seconds: float
    bitrate_kbps: int
    codec: str


class TextMetadata(BaseModel):
    charset: str = Field(..., description="e.g., UTF-8")
    word_count: int


class DocumentMetadata(BaseModel):
    format: str = Field(..., description="e.g., PDF, DOCX")
    size_bytes: int = Field(..., description="File size in bytes")
    page_count: int = Field(..., description="Number of pages, if applicable")


class AssetUploadedBase(BaseModel):
    asset_id: str
    uploader_id: str
    upload_time: datetime
    asset_type: AssetType


class AssetImageUploaded(AssetUploadedBase):
    asset_type: Annotated[AssetType, Field(constant=True)] = AssetType.IMAGE
    metadata: ImageMetadata


class AssetVideoUploaded(AssetUploadedBase):
    asset_type: Annotated[AssetType, Field(constant=True)] = AssetType.VIDEO
    metadata: VideoMetadata


class AssetAudioUploaded(AssetUploadedBase):
    asset_type: Annotated[AssetType, Field(constant=True)] = AssetType.AUDIO
    metadata: AudioMetadata


class AssetTextUploaded(AssetUploadedBase):
    asset_type: Annotated[AssetType, Field(constant=True)] = AssetType.TEXT
    metadata: TextMetadata


class AssetDocumentUploaded(AssetUploadedBase):
    asset_type: Annotated[AssetType, Field(constant=True)] = AssetType.DOCUMENT
    metadata: DocumentMetadata


AssetUploaded = Union[
    AssetImageUploaded,
    AssetVideoUploaded,
    AssetAudioUploaded,
    AssetTextUploaded,
    AssetDocumentUploaded,
]

__all__ = [
    "AssetType",
    "ImageMetadata",
    "VideoMetadata",
    "AudioMetadata",
    "TextMetadata",
    "DocumentMetadata",
    "AssetUploadedBase",
    "AssetImageUploaded",
    "AssetVideoUploaded",
    "AssetAudioUploaded",
    "AssetTextUploaded",
    "AssetDocumentUploaded",
    "AssetUploaded",
]
