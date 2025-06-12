from fastapi import FastAPI
import asyncio
import aio_pika
from core.config import settings
from core.rabbitmq import connect as rabbit_connect
from routes.worker import startup_consumer
from routes.metadata_service import router, on_event

app = FastAPI(title="Metadata Service")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    """
    Initialize RabbitMQ connection and start the asset.uploaded consumer.
    """
    # Initialize connection and channel via core.rabbitmq
    await rabbit_connect()
    # Declare queue and start consuming using worker logic
    await startup_consumer()

@app.on_event("shutdown")
async def shutdown():
    """Clean up RabbitMQ connection on shutdown."""
    from core.rabbitmq import connection
    await connection.close()

app.include_router(router)