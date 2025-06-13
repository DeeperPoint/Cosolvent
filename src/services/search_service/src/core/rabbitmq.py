import logging
import aio_pika
from .config import settings
from ..schemas.search_service_schema import AssetReadyForIndexing
from shared.shared.events import QueueEventNames

logger = logging.getLogger(__name__)

connection: aio_pika.RobustConnection
channel: aio_pika.RobustChannel

async def connect() -> None:
    global connection, channel
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    # Declare or get the events exchange
    await channel.declare_exchange("events", aio_pika.ExchangeType.TOPIC)

async def consume_asset_ready():
    # Declare queue and start consuming AssetReadyForIndexing
    queue = await channel.declare_queue(QueueEventNames.asset_ready_for_indexing, durable=True)
    await queue.consume(on_message)

async def on_message(message: aio_pika.IncomingMessage):
    async with message.process():
        # Parse and log
        event = AssetReadyForIndexing.parse_raw(message.body)
        logger.info(f"Received AssetReadyForIndexing: {event}")
        # Future: buffer/index into Elasticsearch
