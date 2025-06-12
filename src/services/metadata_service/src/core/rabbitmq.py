import aio_pika, asyncio
from .config import settings
from ..schemas.asset import AssetReadyForIndexing

connection: aio_pika.RobustConnection
channel: aio_pika.RobustChannel

async def connect() -> None:
    global connection, channel
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    # declare exchange
    await channel.declare_exchange("events", aio_pika.ExchangeType.TOPIC)

async def publish_ready_for_indexing(evt: AssetReadyForIndexing):
    exchange = await channel.get_exchange("events")
    await exchange.publish(
        aio_pika.Message(body=evt.json().encode()),
        routing_key="asset.ready_for_indexing"
    )