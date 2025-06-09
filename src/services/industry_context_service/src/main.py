from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from motor.motor_asyncio import AsyncIOMotorClient

from routes import files, chunks, search
from database.db import mongo_client, chroma_client

app = FastAPI(
    title="Document Search Service",
    version="1.0.0",
    description="Upload, index, and search documents (PDF, DOCX, PPTX, TXT) via FastAPI + ChromaDB + MongoDB + S3",
)

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(files.router)
app.include_router(chunks.router)
app.include_router(search.router)

@app.get("/health")
async def health_check():
    try:
        await mongo_client.admin.command("ping")
    except Exception:
        raise HTTPException(status_code=503, detail="Cannot reach MongoDB")

    try:
        _ = chroma_client.list_collections()
    except Exception:
        raise HTTPException(status_code=503, detail="Cannot reach ChromaDB")

    return JSONResponse({"status": "ok"})

@app.get("/metrics")
async def metrics():
    return JSONResponse({"uptime_seconds": 0})

