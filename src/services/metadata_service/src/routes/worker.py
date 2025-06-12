import json
import logging
from fastapi import APIRouter
from aio_pika import IncomingMessage
from ..core.rabbitmq import publish_ready_for_indexing
from ..core.asset_client import update_metadata
from ..schemas.asset import AssetUpdatePayload, AssetReadyForIndexing
from core.llm_client import extract_description
from ..core.rabbitmq import channel


router = APIRouter()

async def on_message(msg: IncomingMessage):
    async with msg.process():
        data = json.loads(msg.body)
        # 1) extract description via LLM client
        description = await extract_description(data)
        # 2) update asset
        await update_metadata(AssetUpdatePayload(
            asset_id=data["asset_id"], description=description
        ))
        # 3) publish ready event
        await publish_ready_for_indexing(AssetReadyForIndexing(
            asset_id=data["asset_id"],
            user_id=data["user_id"],
            description=description
        ))

async def startup_consumer():
    """
    Declares the AssetUploaded queue and starts consuming messages with on_message callback.
    """
    queue = await channel.declare_queue("asset.uploaded", durable=True)
    await queue.consume(on_message)

