"""API-key principals for callers with no cookie jar (GAP-1).

A sponsor's backend cannot hold a browser session cookie, so cross-origin access
needs a credential that is not ambient: an API key presented explicitly on every
request.

Keys are stored as a SHA-256 hash. The plaintext is returned exactly once at
issuance and is unrecoverable afterwards, so a leaked database yields no usable
credentials. Lookup is by hash, keeping verification a single indexed query
rather than a scan-and-compare over every stored key.

Two containment properties matter as much as the storage:

  - **Expiry.** A key may carry `expires_at`. Non-expiring credentials are the
    classic audit finding: they outlive the integration, the laptop, and the
    employee.
  - **Scopes.** A key carries an explicit scope set rather than inheriting
    everything its owner can do. Without this, issuing a key to a sponsor's
    integration hands over admin access whenever the issuing user is an admin.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.database import get_collection

# Distinguishes our keys in logs and secret scanners, and lets us reject
# obviously-malformed values before touching the database.
API_KEY_PREFIX = "csk_"
_TOKEN_BYTES = 32

# Scope vocabulary. `read` and `write` cover participant-level API use;
# `admin` is deliberately separate and never granted by default.
SCOPE_READ = "read"
SCOPE_WRITE = "write"
SCOPE_ADMIN = "admin"
VALID_SCOPES = frozenset({SCOPE_READ, SCOPE_WRITE, SCOPE_ADMIN})
DEFAULT_SCOPES = (SCOPE_READ, SCOPE_WRITE)


def generate_api_key() -> str:
    """Return a new plaintext key. Never stored; shown to the caller once."""
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(_TOKEN_BYTES)}"


def hash_api_key(plaintext: str) -> str:
    """Hash a key for storage and lookup.

    A fast hash is deliberate: these are 256-bit random tokens, not user-chosen
    passwords, so there is no dictionary to attack and no need for a slow KDF.
    """
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def looks_like_api_key(value: str | None) -> bool:
    return bool(value) and value.startswith(API_KEY_PREFIX)  # type: ignore[union-attr]


def normalize_scopes(scopes: list[str] | tuple[str, ...] | None) -> list[str]:
    """Validate and de-duplicate a requested scope set."""
    if not scopes:
        return list(DEFAULT_SCOPES)
    invalid = sorted({s for s in scopes if s not in VALID_SCOPES})
    if invalid:
        raise ValueError(f"Unknown scope(s): {', '.join(invalid)}. Valid: {', '.join(sorted(VALID_SCOPES))}")
    return sorted(set(scopes))


def is_expired(record: dict[str, Any]) -> bool:
    expires_at = record.get("expires_at")
    if not expires_at:
        return False
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except ValueError:
            # An unparseable expiry is treated as expired: fail closed.
            return True
    if not isinstance(expires_at, datetime):
        return True
    if expires_at.tzinfo is None:
        return expires_at < datetime.now(timezone.utc).replace(tzinfo=None)
    return expires_at.astimezone(timezone.utc) < datetime.now(timezone.utc)


async def create_api_key(
    user_id: str,
    name: str,
    *,
    scopes: list[str] | None = None,
    expires_in_days: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Issue a key. Returns (plaintext, record) — plaintext is never stored."""
    plaintext = generate_api_key()
    now = datetime.now(timezone.utc)
    doc: dict[str, Any] = {
        "user_id": str(user_id),
        "name": name,
        "key_hash": hash_api_key(plaintext),
        # Shown in listings so an operator can identify a key without revealing it.
        "key_hint": plaintext[-4:],
        "scopes": normalize_scopes(scopes),
        "expires_at": now + timedelta(days=expires_in_days) if expires_in_days else None,
        "revoked": False,
        "created_at": now,
        "last_used_at": None,
    }
    result = await get_collection("api_keys").insert_one(doc)
    doc["_id"] = result.inserted_id
    return plaintext, doc


async def resolve_api_key(plaintext: str) -> dict[str, Any] | None:
    """Return the owning user for a valid, unrevoked, unexpired key, else None.

    The returned user carries `auth_method="api_key"` and the key's scopes, so
    downstream dependencies can treat a key principal differently from a logged-in
    human — which is what stops a key from reaching admin routes or minting
    further keys.
    """
    if not looks_like_api_key(plaintext):
        return None

    keys = get_collection("api_keys")
    record = await keys.find_one({"key_hash": hash_api_key(plaintext)})
    if not record or record.get("revoked") or is_expired(record):
        return None

    user = await get_collection("users").find_one({"_id": record["user_id"]})
    if not user or user.get("is_active") is False:
        return None

    user["auth_method"] = "api_key"
    user["scopes"] = list(record.get("scopes") or DEFAULT_SCOPES)
    user["api_key_id"] = str(record.get("_id"))

    # Best-effort usage stamp; a failure here must not deny an otherwise valid request.
    try:
        await keys.update_one(
            {"_id": record["_id"]}, {"$set": {"last_used_at": datetime.now(timezone.utc)}}
        )
    except Exception:  # noqa: BLE001 - telemetry only
        pass

    return user


async def list_api_keys(user_id: str) -> list[dict[str, Any]]:
    """List a user's keys without exposing any secret material."""
    records = (
        await get_collection("api_keys")
        .find({"user_id": str(user_id)})
        .sort("created_at", -1)
        .to_list(length=None)
    )
    return [
        {
            "id": str(r.get("_id")),
            "name": r.get("name"),
            "key_hint": r.get("key_hint"),
            "scopes": list(r.get("scopes") or []),
            "revoked": bool(r.get("revoked")),
            "expired": is_expired(r),
            "expires_at": r.get("expires_at"),
            "created_at": r.get("created_at"),
            "last_used_at": r.get("last_used_at"),
        }
        for r in records
    ]


async def revoke_api_key(user_id: str, key_id: str) -> bool:
    """Revoke a key the user owns. Scoped by user_id so one caller cannot revoke another's."""
    result = await get_collection("api_keys").update_one(
        {"_id": key_id, "user_id": str(user_id)}, {"$set": {"revoked": True}}
    )
    return bool(getattr(result, "modified_count", 0))
