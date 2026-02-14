"""Motor (async MongoDB) connection management."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client[settings.mongodb_database]
    await _ensure_indexes()


async def close_db() -> None:
    global _client, _db
    if _client:
        _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not connected")
    return _db


def get_collection(name: str) -> AsyncIOMotorCollection:
    return get_db()[name]


async def _ensure_indexes() -> None:
    """Create required indexes on startup."""
    db = get_db()

    # users
    await db.users.create_index("email", unique=True)

    # sessions – TTL index handled by session_ttl
    await db.sessions.create_index("token", unique=True)
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)

    # profiles
    await db.profiles.create_index("user_id")
    await db.profiles.create_index("participant_type")
    await db.profiles.create_index([("participant_type", 1), ("status", 1)])

    # drafts
    await db.drafts.create_index("user_id", unique=True)

    # applications
    await db.applications.create_index("user_id")
    await db.applications.create_index("status")

    # files
    await db.files.create_index("user_id")
    await db.files.create_index("profile_id")

    # private_assets
    await db.private_assets.create_index("user_id")

    # conversations
    await db.conversations.create_index("participants.user_id")
    await db.conversations.create_index("status")

    # messages
    await db.messages.create_index("conversation_id")
    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])

    # notifications
    await db.notifications.create_index("user_id")
    await db.notifications.create_index([("user_id", 1), ("is_read", 1)])

    # FAQs
    await db.faqs.create_index("is_active")
    await db.faqs.create_index("sort_order")

    # AI collections
    await db.ai_documents.create_index("status")
    await db.ai_chat_history.create_index("user_id")
    await db.ai_chat_history.create_index("thread_id")
