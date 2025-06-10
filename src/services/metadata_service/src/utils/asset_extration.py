import httpx
import asyncio
from io import BytesIO
from PyPDF2 import PdfReader
from docx import Document
import textract
from typing import Optional
from bson import ObjectId
from src.database.db import db
from src.database.models.metadata_service import AssetModel
from src.database.crud.metadata_service_crud import AssetCRUD
from src.utils.mock_llm_extraction import ExtractUsingLLM
import boto3
from src.core.config import Settings 
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

class AssetExtraction:
    """
    Service for reading asset contents from an S3-compatible URL.
    """

    SUPPORTED_TYPES = {
        "plain",
        "pdf",
        "msword",
        "vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    @staticmethod
    async def read_from_s3(url: str, content_type: str) -> str:
        """
        Fetches the file from the given S3 URL using the S3 API and returns its text content based on MIME type.

        :param url: Public or pre-signed S3 URL of the asset
        :param file_type: MIME type of the asset
        :returns: Extracted text content
        :raises ValueError: If file_type is unsupported or URL invalid
        """
        # Parse S3 URL to bucket and key
        parsed = urlparse(url)
        parts = parsed.path.lstrip("/").split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 URL: {url}")
        bucket, key = parts
        # Download object via S3 API
        s3 = boto3.client(
            "s3",
            endpoint_url=Settings.Config.S3_ENDPOINT,
            aws_access_key_id=Settings.Config.S3_ACCESS_KEY,
            aws_secret_access_key=Settings.Config.S3_SECRET_KEY,
        )
        response = s3.get_object(Bucket=bucket, Key=key)
        # Read body asynchronously
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, response["Body"].read)

        # Dispatch based on MIME type
        content_type = content_type.split("/")[1]
        if content_type == "plain":
            return str(data.decode('utf-8'))

        if content_type == "pdf":
            reader = PdfReader(BytesIO(data))
            return "\n\n".join((page.extract_text() or "") for page in reader.pages)
        if content_type == "msword":
            return str(textract.process(input_data=data, extension='doc').decode('utf-8'))

        if content_type == "vnd.openxmlformats-officedocument.wordprocessingml.document":
            with BytesIO(data) as bio:
                doc = Document(bio)
                return "\n\n".join(p.text for p in doc.paragraphs)
        
        else:
            return ExtractUsingLLM(url , content_type).extract()
    @staticmethod
    async def read_asset_by_id(asset_id: str) -> Optional[str]:
        """
        Fetches asset metadata from the database, then reads its content from S3 if supported.

        :param asset_id: MongoDB ObjectId string
        :returns: Extracted text or None if asset not found
        """
        raw = await AssetCRUD.get_by_id(asset_id)
        if not raw:
            return None

        asset_url = raw["url"]
        file_type = raw["content_type"]
        return await AssetExtraction.read_from_s3(asset_url,  file_type)
