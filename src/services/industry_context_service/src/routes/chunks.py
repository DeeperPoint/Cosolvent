from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from typing import List

from app.database import chunks_collection
from app.schemas import ChunkResponse

router = APIRouter(prefix="/files/{file_id}/chunks", tags=["chunks"])

@router.get("", response_model=List[ChunkResponse])
async def list_chunks(
    file_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    cursor = chunks_collection.find({"file_id": file_id}).sort("offset", 1).skip(offset).limit(limit)
    chunks = []
    async for doc in cursor:
        chunks.append(ChunkResponse(
            chunk_id=doc["chunk_id"],
            text=doc["text"],
            offset=doc["offset"],
        ))
    return chunks
