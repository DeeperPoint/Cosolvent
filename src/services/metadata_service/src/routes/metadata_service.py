# import logging
# from fastapi import APIRouter, HTTPException
# from aio_pika import IncomingMessage
# import httpx

# from core.config import settings
# from schemas.metadata_service_schema import AssetUploadedEvent, MetadataResponse

# logger = logging.getLogger("metadata_service.router")
# router = APIRouter()

# @router.post("/describe/{asset_id}", response_model=MetadataResponse)
# async def describe_asset(asset_id: str):
#     """
#     HTTP trigger to describe an asset by ID.
#     """
#     return await process_asset(asset_id)

# async def process_asset(asset_id: str) -> MetadataResponse:
#     """
#     Fetch asset bytes and call LLM to generate description.
#     """
#     # 1) Fetch asset metadata (to get download URL) from Asset Service
#     list_url = f"{settings.asset_service_url.rstrip('/')}/assets"
#     params = {"asset_id": asset_id}
#     resp_meta = await shared_http_client.get(list_url, params=params)
#     resp_meta.raise_for_status()
#     assets = resp_meta.json()
#     if not assets:
#         raise HTTPException(status_code=404, detail="Asset not found")
#     asset_info = assets[0]
#     download_url = asset_info.get("url")
#     if not is_valid_url(download_url):
#         raise HTTPException(status_code=400, detail="Invalid download URL")
#     # 2) Download binary data
#     resp_file = await shared_http_client.get(download_url)
#     resp_file.raise_for_status()
#     data = resp_file.content
#     # TODO: handle audio, video, PDF, DOCX; for now only images
#     files = {"file": (f"{asset_id}", data, asset_info.get("content_type", "application/octet-stream"))}
#     # 3) Call LLM Orchestration metadata endpoint
#     llm_resp = await shared_http_client.post(
#         f"{settings.llm_orchestration_service_url.rstrip('/')}/llm/metadata",
#         files=files
#     )
#     llm_resp.raise_for_status()
#     payload = llm_resp.json()
#         # unwrap LLMServiceResponse wrapper
#         result = payload.get("result", payload)

#     description = result.get("description", "")
#     logger.info(f"Described asset {asset_id}: {description}")
#     return MetadataResponse(asset_id=asset_id, description=description)

# async def on_event(message: IncomingMessage):
#     """
#     RabbitMQ AssetUploaded event handler.
#     """
#     async with message.process(ignore_processed=True):
#         body = message.body.decode()
#         event = AssetUploadedEvent.parse_raw(body)

#         # Only process images for now
#         if event.media_type.startswith("image/"):
#             meta = await process_asset(event.asset_id)
#             logger.info(f"Processed AssetUploaded event: {meta}")
#         else:
#             logger.info(f"Skipping non-image asset {event.asset_id}")
