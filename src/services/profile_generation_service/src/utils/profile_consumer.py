import time
start = time.time()
import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor  # retained if needed
import aio_pika
from src.core.config import Settings
from src.database.crud.profile_generation_service_crud import PROFILECRUD
from shared.events import QueueEventNames
from src.utils.mock_profile_generation_llm import LLMPROFILEGENERATION
from src.utils.publisher import publish_profile_generated_event
import sys

# Configure logging
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

# (No thread pool needed; all operations use async I/O)
# executor = ThreadPoolExecutor()

async def process_metadata(message: aio_pika.IncomingMessage):
    async with message.process():
        try:
            logger.info("Processing metadata...")
            data = json.loads(message.body.decode())
            # Extract job details and resume_path
            asset_id = data.get("asset_id")
            
            user_id = data.get("user_id")
            # Fetch existing metadata and profile
            metadata = await PROFILECRUD.get_metadata_by_asset_id(asset_id)
            cur_profile = await PROFILECRUD.get_by_id(asset_id)
            print('the current profile is', cur_profile)
            print('the metadata is', metadata)
            # Generate new profile via mock LLM
            llm = LLMPROFILEGENERATION(cur_profile, metadata)
            generated_profile = llm.generate_profile()
            # Convert to dict if Pydantic model
            profile_data = generated_profile.dict() if hasattr(generated_profile, 'dict') else generated_profile
            await PROFILECRUD.create(profile_data)
            await publish_profile_generated_event({
                "user_id": user_id,
            })
            logger.info(f"profile for asset {asset_id} processed successfully with generated profile: {generated_profile}")


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
            queue = await channel.declare_queue(QueueEventNames.metadata_completed, durable=True)

            logger.info(" [*] Waiting for messages. To exit press CTRL+C")
            await queue.consume(process_metadata)

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
