import io, os
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from uuid import uuid4
import boto3
from botocore.exceptions import ClientError
from src.utils.publisher import publish_asset
from src.schemas.asset_service_schema import AssetCreate, AssetResponse
from src.database.crud.asset_service_crud import AssetCRUD
from src.core.config import Config
from fastapi import Query
from bson import ObjectId

router = APIRouter()

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    # Images
    "image/png", "image/jpeg", "image/webp",
    # Videos
    "video/mp4", "video/mpeg",
    # Audio
    "audio/mpeg", "audio/wav",
    # Text
    "text/plain",
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

s3_client = boto3.client(
    "s3",
    endpoint_url=Config.S3_ENDPOINT,
    aws_access_key_id=Config.S3_ACCESS_KEY,
    aws_secret_access_key=Config.S3_SECRET_KEY,
)
# Ensure the target bucket exists (idempotent)
try:
    s3_client.create_bucket(Bucket=Config.S3_BUCKET)
except ClientError:
    # ignore if bucket already exists or access issues
    pass

@router.post("/assets", response_model=AssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    # Validate MIME
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    data = await file.read()
    key = f"{uuid4().hex}-{file.filename}"
    
    # Upload, ensure bucket exists
    try:
        s3_client.upload_fileobj(
            io.BytesIO(data),
            Config.S3_BUCKET,
            key,
            ExtraArgs={"ContentType": file.content_type},
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "NoSuchBucket":
            # create bucket then retry
            s3_client.create_bucket(Bucket=Config.S3_BUCKET)
            s3_client.upload_fileobj(
                io.BytesIO(data),
                Config.S3_BUCKET,
                key,
                ExtraArgs={"ContentType": file.content_type},
            )
        else:
            raise HTTPException(status_code=500, detail=str(e))

    url = f"{Config.S3_ENDPOINT}/{Config.S3_BUCKET}/{key}"
    file_type = file.content_type.split("/")[0]

    asset_data = {
        "user_id": user_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "file_type": file_type,
        "url": url,
    }


    saved = await AssetCRUD.create(asset_data)

    await publish_asset({
            "asset_id": str(saved["id"]),
        })
    return saved



@router.get("/assets", response_model=list[AssetResponse])
async def get_assets(
    user_id: str = Query(None),
    asset_id: str = Query(None)
):
    if asset_id:
        # Validate asset_id as a valid ObjectId
        try:
            ObjectId(asset_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid asset_id format")
        asset = await AssetCRUD.get_by_id(asset_id)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        return [asset]
    elif user_id:
        if not user_id.strip():
            raise HTTPException(status_code=400, detail="user_id cannot be empty")
        assets = await AssetCRUD.get_by_user_id(user_id)
        return assets
    else:
        raise HTTPException(status_code=400, detail="Either user_id or asset_id must be provided")
