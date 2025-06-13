import pytest
import asyncio
from core import rabbitmq
from aio_pika import Message
from schemas.asset import AssetReadyForIndexing

# Dummy classes to simulate aio_pika connection, channel, and exchange
class DummyExchange:
    def __init__(self):
        self.published = []
    async def publish(self, message: Message, routing_key: str):
        self.published.append((message, routing_key))

class DummyChannel:
    def __init__(self, exchange):
        self._exchange = exchange
    async def declare_exchange(self, name, type):
        return self._exchange
    async def get_exchange(self, name):
        return self._exchange

class DummyConnection:
    def __init__(self, channel):
        self._channel = channel
    async def channel(self):
        return self._channel
    async def close(self):
        pass

@pytest.mark.asyncio
async def test_publish_ready_for_indexing(monkeypatch):
    # Setup dummy exchange and channel
    exchange = DummyExchange()
    channel = DummyChannel(exchange)
    connection = DummyConnection(channel)

    # Monkeypatch connect_robust and internal channel state
    async def dummy_connect(url):
        return connection
    monkeypatch.setattr(rabbitmq, 'connect', lambda: dummy_connect(''))
    # Need to call actual connect() to set rabbitmq.channel
    # But our rabbitmq.connect() sets global channel, not via connect()
    # So directly assign module globals
    rabbitmq.connection = connection
    rabbitmq.channel = channel

    # Create test event
    event = AssetReadyForIndexing(asset_id="1234", user_id="5678", description="Test")

    # Publish and assert
    await rabbitmq.publish_ready_for_indexing(event)
    assert len(exchange.published) == 1
    message, routing_key = exchange.published[0]
    assert routing_key == 'asset.ready_for_indexing'
    assert message.body == event.json().encode()
    
    # Clean up
    await connection.close()
