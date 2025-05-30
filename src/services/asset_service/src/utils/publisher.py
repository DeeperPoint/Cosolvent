import aio_pika
from shared.events import QueueEventNames
from tenacity import retry, wait_fixed, stop_after_attempt
import json
import logging
from src.core.config import Config
logging.basicConfig(level=logging.INFO)

@retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
async def publish_asset(message):
    """Publishes a message to RabbitMQ with retry handling."""
    try:
        connection = await aio_pika.connect_robust(Config.RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(QueueEventNames.asset_upload, durable=True)
            
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message, ensure_ascii=False).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=QueueEventNames.asset_upload
            )
        logging.info(f"Message sent successfully for asset_id_id:  {message.get('asset_id')}")
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        raise  # Re-raise to trigger retry

