from fastapi import APIRouter, HTTPException
from typing import List
from uuid import UUID

from app.schemas import SearchRequest, SearchResult
from app.database import chroma_collection, get_embedding

router = APIRouter(prefix="/search", tags=["search"])

@router.post("", response_model=List[SearchResult])
async def semantic_search(request: SearchRequest):
    embedding = await get_embedding(request.query)

    where = {}
    if request.filters:
        if request.filters.country:
            where["country"] = {"$in": request.filters.country}

        if request.filters.date:
            date_filter = {}
            if request.filters.date.gte:
                date_filter["$gte"] = request.filters.date.gte
            if request.filters.date.lte:
                date_filter["$lte"] = request.filters.date.lte
            if date_filter:
                where["date"] = date_filter

    try:
        results = chroma_collection.query(
            query_embeddings=[embedding],
            n_results=request.top_k,
            where=where if where else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Vector search failed")


    hits = []
    for idx, cid in enumerate(results.get("ids", [[]])[0]):
        score = float(results["distances"][0][idx])
        metadata = results["metadatas"][0][idx]
        text = results["documents"][0][idx]
        hits.append(SearchResult(
            file_id=UUID(metadata["file_id"]),
            chunk_id=UUID(metadata["chunk_id"]),
            text=text,
            score=score,
            metadata={"country": metadata.get("country"), "date": metadata.get("date")},
        ))
    return hits
