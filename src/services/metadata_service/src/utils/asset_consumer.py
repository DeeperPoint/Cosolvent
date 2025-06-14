import time
start = time.time()
import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor  # retained if needed
import aio_pika
from src.core.config import Settings
from src.utils.asset_extration import AssetExtraction
from src.database.crud.metadata_service_crud import AssetCRUD
from shared.events import QueueEventNames
from src.utils.asset_publisher import publish_metadata_extraction_completed

import sys

# Configure logging
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

# (No thread pool needed; all operations use async I/O)
# executor = ThreadPoolExecutor()

async def process_asset(message: aio_pika.IncomingMessage):
    async with message.process():
        try:
            logger.info("Processing asset...")
            data = json.loads(message.body.decode())
            # Extract job details and resume_path
            asset_id = data.get("asset_id")
            

            # Extract description asynchronously
            description = await AssetExtraction.read_asset_by_id(asset_id)
            # make the description in one line
            description = description.replace("\n", " ").strip()
            asset = await AssetCRUD.get_by_id(asset_id)
            user_id = asset["user_id"]

            if not user_id:
                logger.error(f"User ID not found for asset_id: {asset_id}")
                return
            await AssetCRUD.add_description(asset_id, description)
            await publish_metadata_extraction_completed({
                "asset_id": asset_id,
                "user_id": user_id
            })
            logger.info(f"Asset {asset_id} processed successfully with description: {description[:30]}")


        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from message body.")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

async def consume_messages():
    """Consumes messages from RabbitMQ and processes them."""
    try:
        logger.info("Starting consumer...")
        connection = await aio_pika.connect_robust(Settings.Config.RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(QueueEventNames.asset_upload, durable=True)

            logger.info(" [*] Waiting for messages. To exit press CTRL+C")
            await queue.consume(process_asset)

            # Keep running indefinitely
            await asyncio.Future()
    except Exception as e:
        logger.exception(f"Error in message consumption: {e}")

if __name__ == "__main__":
    try:
        print(f"Consumer script started, time taken: {time.time() - start}")
        logger.info("CONSUMER RUNNING")
        asyncio.run(consume_messages())
    except KeyboardInterrupt:
        logger.info("Shutting down consumer...")
