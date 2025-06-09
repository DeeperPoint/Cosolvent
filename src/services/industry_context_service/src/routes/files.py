import os
from uuid import uuid4, UUID
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
import boto3

from app.database import files_collection, chunks_collection, chroma_collection, get_embedding, create_mongo_indexes
from app.schemas import (
    FileMetadataCreate, FileMetadataUpdate, FileMetadataResponse
)
from app.utils.text_extraction import (
    extract_text_from_pdf, extract_text_from_docx,
    extract_text_from_pptx, extract_text_from_txt, chunk_text
)

from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/files", tags=["files"])

# S3 client
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
s3_bucket = os.getenv("S3_BUCKET")
s3_client = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
)

@router.on_event("startup")
async def startup_indexes():
    await create_mongo_indexes()


@router.post("/", response_model=FileMetadataResponse)
async def upload_file(
    file: UploadFile = File(...),
    country: str = Form(...),
    date: str = Form(...),
):
    allowed_types = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.openxmlformats-officedocument.presentationml.presentation", "text/plain"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type", code="invalid_file")

    file_id = uuid4()
    filename = file.filename
    content_type = file.content_type
    uploaded_at = datetime.utcnow()
    status = "processing"
    s3_key = f"documents/{file_id}/{filename}"

    file_doc = {
        "file_id": file_id,
        "filename": filename,
        "content_type": content_type,
        "country": country,
        "date": date,
        "s3_key": s3_key,
        "uploaded_at": uploaded_at,
        "status": status,
    }
    await files_collection.insert_one(file_doc)

    file_bytes = await file.read()
    try:
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
        )
    except Exception as e:
        # Roll back metadata
        await files_collection.delete_one({"file_id": file_id})
        raise HTTPException(status_code=500, detail="S3 upload failed")

    if content_type == "application/pdf":
        text = extract_text_from_pdf(file_bytes)
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = extract_text_from_docx(file_bytes)
    elif content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        text = extract_text_from_pptx(file_bytes)
    elif content_type == "text/plain":
        text = extract_text_from_txt(file_bytes)
    else:
        text = ""

    nchunks = chunk_text(text)

    embeddings = []
    metadata_list = []
    chunk_id_list = []
    offset_list = []
    chunk_texts = []

    for c in nchunks:
        cid = c["chunk_id"]
        ctext = c["text"]
        coffset = c["offset"]

        embed = await get_embedding(ctext)

        embeddings.append(embed)
        metadata_list.append({
            "file_id": str(file_id),
            "country": country,
            "date": date,
            "chunk_id": str(cid),
            "offset": coffset,
        })
        chunk_id_list.append(str(cid))
        offset_list.append(coffset)
        chunk_texts.append(ctext)

    # Upsert to ChromaDB
    chroma_collection.add(
        embeddings=embeddings,
        ids=chunk_id_list,
        metadatas=metadata_list,
        documents=chunk_texts,
    )

    chunk_docs = []
    for idx, cid in enumerate(chunk_id_list):
        doc = {
            "chunk_id": cid,
            "file_id": file_id,
            "text": chunk_texts[idx],
            "vector_id": cid,
            "offset": offset_list[idx],
        }
        chunk_docs.append(doc)
    if chunk_docs:
        await chunks_collection.insert_many(chunk_docs)

    await files_collection.update_one({"file_id": file_id}, {"$set": {"status": "ready"}})

    return FileMetadataResponse(
        file_id=file_id,
        filename=filename,
        country=country,
        date=date,
        status="ready",
        uploaded_at=uploaded_at,
    )


@router.get("/", response_model=list[FileMetadataResponse])
async def list_files():
    cursor = files_collection.find({})
    result = []
    async for doc in cursor:
        result.append(FileMetadataResponse(
            file_id=doc["file_id"],
            filename=doc["filename"],
            country=doc["country"],
            date=doc["date"],
            status=doc["status"],
            uploaded_at=doc["uploaded_at"],
        ))
    return result


@router.get("/{file_id}", response_model=FileMetadataResponse)
async def get_file_metadata(file_id: UUID):
    doc = await files_collection.find_one({"file_id": file_id})
    if not doc:
        raise HTTPException(status_code=404, detail="File not found")
    return FileMetadataResponse(
        file_id=doc["file_id"],
        filename=doc["filename"],
        country=doc["country"],
        date=doc["date"],
        status=doc["status"],
        uploaded_at=doc["uploaded_at"],
    )


@router.put("/{file_id}", response_model=FileMetadataResponse)
async def update_file(
    file_id: UUID,
    country: str | None = Form(None),
    date: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    existing = await files_collection.find_one({"file_id": file_id})
    if not existing:
        raise HTTPException(status_code=404, detail="File not found")

    update_data = {}
    if country:
        update_data["country"] = country
    if date:
        update_data["date"] = date

    if file:
        file_bytes = await file.read()
        try:
            s3_client.put_object(
                Bucket=s3_bucket,
                Key=existing["s3_key"],
                Body=file_bytes,
                ContentType=file.content_type,
            )
        except Exception:
            raise HTTPException(status_code=500, detail="S3 overwrite failed")

        # Re-extract, re-chunk, re-index: delete previous chunks and chroma entries
        await chunks_collection.delete_many({"file_id": file_id})
        try:
            chroma_collection.delete(where={"file_id": str(file_id)})
        except Exception:
            pass

        # Extract text+chunk+re-index (similar to upload)
        if file.content_type == "application/pdf":
            text = extract_text_from_pdf(file_bytes)
        elif file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text = extract_text_from_docx(file_bytes)
        elif file.content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
            text = extract_text_from_pptx(file_bytes)
        elif file.content_type == "text/plain":
            text = extract_text_from_txt(file_bytes)
        else:
            text = ""

        nchunks = chunk_text(text)
        embeddings, metadatas, chunk_ids, offsets, texts = [], [], [], [], []
        for c in nchunks:
            cid = c["chunk_id"]
            ctext = c["text"]
            coffset = c["offset"]
            embed = await get_embedding(ctext)
            embeddings.append(embed)
            metadatas.append({
                "file_id": str(file_id),
                "country": country or existing["country"],
                "date": date or existing["date"],
                "chunk_id": str(cid),
                "offset": coffset,
            })
            chunk_ids.append(str(cid))
            offsets.append(coffset)
            texts.append(ctext)

        chroma_collection.add(
            embeddings=embeddings,
            ids=chunk_ids,
            metadatas=metadatas,
            documents=texts,
        )
        chunk_docs = []
        for idx, cid in enumerate(chunk_ids):
            chunk_docs.append({
                "chunk_id": cid,
                "file_id": file_id,
                "text": texts[idx],
                "vector_id": cid,
                "offset": offsets[idx],
            })
        if chunk_docs:
            await chunks_collection.insert_many(chunk_docs)

    if update_data:
        await files_collection.update_one({"file_id": file_id}, {"$set": update_data})

    doc = await files_collection.find_one({"file_id": file_id})
    return FileMetadataResponse(
        file_id=doc["file_id"],
        filename=doc["filename"],
        country=doc["country"],
        date=doc["date"],
        status=doc["status"],
        uploaded_at=doc["uploaded_at"],
    )


@router.delete("/{file_id}")
async def delete_file(file_id: UUID):
    existing = await files_collection.find_one({"file_id": file_id})
    if not existing:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        s3_client.delete_object(Bucket=s3_bucket, Key=existing["s3_key"])
    except Exception:
        pass

    await chunks_collection.delete_many({"file_id": file_id})

    try:
        chroma_collection.delete(where={"file_id": str(file_id)})
    except Exception:
        pass

    await files_collection.delete_one({"file_id": file_id})
    return JSONResponse(status_code=204, content=None)