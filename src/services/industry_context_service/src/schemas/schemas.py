from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime



class FileInDB(BaseModel):
    _id: Optional[str]
    file_id: UUID
    filename: str
    content_type: str
    country: str
    date: str
    s3_key: str
    uploaded_at: datetime
    status: str

class ChunkInDB(BaseModel):
    _id: Optional[str]
    chunk_id: UUID
    file_id: UUID
    text: str
    vector_id: str
    offset: int




class FileMetadataCreate(BaseModel):
    country: str = Field(..., description="ISO country code")
    date: str = Field(..., regex=r"\d{4}-\d{2}-\d{2}")

class FileMetadataUpdate(BaseModel):
    country: Optional[str] = Field(None, description="ISO country code")
    date: Optional[str] = Field(None, regex=r"\d{4}-\d{2}-\d{2}")

class FileMetadataResponse(BaseModel):
    file_id: UUID
    filename: str
    country: str
    date: str
    status: str
    uploaded_at: datetime

class ChunkResponse(BaseModel):
    chunk_id: UUID
    text: str
    offset: int

class SearchFilterDate(BaseModel):
    gte: Optional[str] = Field(None, regex=r"\d{4}-\d{2}-\d{2}")
    lte: Optional[str] = Field(None, regex=r"\d{4}-\d{2}-\d{2}")

class SearchFilters(BaseModel):
    country: Optional[List[str]]
    date: Optional[SearchFilterDate]

class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(5, ge=1)
    filters: Optional[SearchFilters]

class SearchResult(BaseModel):
    file_id: UUID
    chunk_id: UUID
    text: str
    score: float
    metadata: dict
