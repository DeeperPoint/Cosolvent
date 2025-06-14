import aio_pika
from shared.events import QueueEventNames
from tenacity import retry, wait_fixed, stop_after_attempt
import json
import logging
from src.core.config import Settings
logging.basicConfig(level=logging.INFO)

@retry(wait=wait_fixed(2), stop=stop_after_attempt(5))
async def publish_profile_generated_event(message):
    """Publishes a message to RabbitMQ with retry handling."""
    try:
        connection = await aio_pika.connect_robust(Settings.Config.RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(QueueEventNames.profile_generation_completed, durable=True)
            
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(message, ensure_ascii=False).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                ),
                routing_key=QueueEventNames.profile_generation_completed
            )
        logging.info(f"Profile generation Event sent successfully for user_id:  {message.get('user_id')}")
    except Exception as e:
        logging.error(f"Failed to send profile generated event: {e}")
        raise  # Re-raise to trigger retry

