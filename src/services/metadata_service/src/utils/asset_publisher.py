import aio_pika
from shared.events import QueueEventNames
from tenacity import retry, wait_fixed, stop_after_attempt
import json
import logging
from src.core.config import Settings
logging.basicConfig(level=logging.INFO)

@retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
async def publish_metadata_extraction_completed(message):
    """Publishes a message to RabbitMQ with retry handling."""
    try:
        connection = await aio_pika.connect_robust(Settings.Config.RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(QueueEventNames.metadata_completed, durable=True)
            
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message, ensure_ascii=False).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=QueueEventNames.metadata_completed
            )
        logging.info(f"Queue publish successfully to metadata completed for asset_id:  {message.get('asset_id')}")
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        raise  # Re-raise to trigger retry

