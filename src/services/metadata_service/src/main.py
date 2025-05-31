from fastapi import FastAPI
import asyncio
import aio_pika
from core.config import settings
from routes.metadata_service import router, on_event

app = FastAPI(title="Metadata Service")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    # Connect to RabbitMQ and start consuming AssetUploaded events
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    queue = await channel.declare_queue("asset.uploaded", durable=True)
    await queue.consume(on_event)
    app.state.rabbitmq_connection = connection

@app.on_event("shutdown")
async def shutdown():
    await app.state.rabbitmq_connection.close()

app.include_router(router)