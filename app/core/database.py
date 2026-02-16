"""Postgres database connection + Mongo-style collection compatibility layer."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, String, and_, cast, func, not_, or_, select, text, update
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.types import Integer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db_schema import metadata, table_for_collection

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_db_proxy: "DatabaseProxy" | None = None


@dataclass
class InsertOneResult:
    inserted_id: str


@dataclass
class DeleteResult:
    deleted_count: int


@dataclass
class UpdateResult:
    matched_count: int
    modified_count: int


class AggregateCursor:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows
        self._idx = 0

    def __aiter__(self) -> "AggregateCursor":
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._idx >= len(self._rows):
            raise StopAsyncIteration
        value = self._rows[self._idx]
        self._idx += 1
        return value


class CollectionCursor:
    def __init__(
        self,
        collection: "CollectionProxy",
        query: dict[str, Any] | None,
        projection: dict[str, Any] | None,
    ):
        self._collection = collection
        self._query = query or {}
        self._projection = projection
        self._sort_fields: list[tuple[str, int]] = []
        self._skip = 0
        self._limit: int | None = None

    def sort(self, key: str, direction: int) -> "CollectionCursor":
        self._sort_fields.append((key, direction))
        return self

    def skip(self, n: int) -> "CollectionCursor":
        self._skip = max(0, n)
        return self

    def limit(self, n: int) -> "CollectionCursor":
        self._limit = max(0, n)
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        docs = await self._collection._find_docs(
            self._query,
            self._projection,
            self._sort_fields,
            self._skip,
            self._limit,
        )
        if length is not None and length >= 0:
            return docs[:length]
        return docs


class DatabaseProxy:
    def __getattr__(self, item: str) -> "CollectionProxy":
        return get_collection(item)


class CollectionProxy:
    def __init__(self, name: str):
        self.name = name
        self.table = table_for_collection(name)
        self.database = get_db()

    async def insert_one(self, doc: dict[str, Any]) -> InsertOneResult:
        payload = _serialize_json(dict(doc))
        raw_id = payload.pop("_id", None)
        doc_id = _coerce_uuid(raw_id) if raw_id else uuid.uuid4()

        async with session_scope() as session:
            await session.execute(
                self.table.insert().values(
                    id=doc_id,
                    data=payload,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        return InsertOneResult(inserted_id=str(doc_id))

    def find(
        self,
        query: dict[str, Any] | None = None,
        projection: dict[str, Any] | None = None,
    ) -> CollectionCursor:
        return CollectionCursor(self, query, projection)

    async def find_one(
        self,
        query: dict[str, Any] | None = None,
        projection: dict[str, Any] | None = None,
        sort: list[tuple[str, int]] | None = None,
    ) -> dict[str, Any] | None:
        docs = await self._find_docs(query or {}, projection, sort or [], 0, 1)
        return docs[0] if docs else None

    async def find_one_and_update(
        self,
        query: dict[str, Any],
        update_doc: dict[str, Any],
        *,
        upsert: bool = False,
        return_document: bool = True,
        projection: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        async with session_scope() as session:
            if upsert:
                # Serialize upserts for the same logical key to avoid duplicate inserts.
                lock_key = self._upsert_lock_key(query)
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                    {"lock_key": lock_key},
                )

            current = await self._find_one_for_update(session, query)
            if current is None:
                if not upsert:
                    return None
                base_doc = _doc_from_filter(query)
                base_doc.update(update_doc.get("$setOnInsert", {}))
                base_doc.update(update_doc.get("$set", {}))

                payload = _serialize_json(dict(base_doc))
                raw_id = payload.pop("_id", None)
                doc_id = _coerce_uuid(raw_id) if raw_id else uuid.uuid4()
                await session.execute(
                    self.table.insert().values(
                        id=doc_id,
                        data=payload,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

                if not return_document:
                    return None
                inserted = _deserialize_json(dict(payload))
                inserted["_id"] = str(doc_id)
                return _apply_projection(inserted, projection)

            updated = _apply_update(current, update_doc, is_insert=False)
            payload = _serialize_json({k: v for k, v in updated.items() if k != "_id"})
            doc_id = _coerce_uuid(current["_id"])

            await session.execute(
                update(self.table)
                .where(self.table.c.id == doc_id)
                .values(
                    data=payload,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
            if not return_document:
                return None
            return _apply_projection(updated, projection)

    async def update_one(self, query: dict[str, Any], update_doc: dict[str, Any]) -> UpdateResult:
        async with session_scope() as session:
            current = await self._find_one_for_update(session, query)
            if not current:
                return UpdateResult(matched_count=0, modified_count=0)

            updated = _apply_update(current, update_doc, is_insert=False)
            payload = _serialize_json({k: v for k, v in updated.items() if k != "_id"})
            doc_id = _coerce_uuid(current["_id"])

            await session.execute(
                update(self.table)
                .where(self.table.c.id == doc_id)
                .values(
                    data=payload,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
            return UpdateResult(matched_count=1, modified_count=1)

    async def delete_one(self, query: dict[str, Any]) -> DeleteResult:
        async with session_scope() as session:
            current = await self._find_one_for_update(session, query)
            if not current:
                return DeleteResult(deleted_count=0)

            await session.execute(self.table.delete().where(self.table.c.id == _coerce_uuid(current["_id"])))
            await session.commit()
            return DeleteResult(deleted_count=1)

    async def count_documents(self, query: dict[str, Any] | None = None) -> int:
        predicate = self._supported_predicate(query or {})
        statement = select(func.count()).select_from(self.table)
        if predicate is not None:
            statement = statement.where(predicate)
        async with session_scope() as session:
            return int((await session.execute(statement)).scalar_one())

    async def aggregate(self, pipeline: list[dict[str, Any]]) -> AggregateCursor:
        match_stage = {}
        group_stage = {}
        for stage in pipeline:
            if "$match" in stage:
                match_stage = stage["$match"]
            elif "$group" in stage:
                group_stage = stage["$group"]

        field = str(group_stage.get("_id", "")).lstrip("$")
        if field and group_stage.get("count") == {"$sum": 1}:
            predicate, fully_supported = self._compile_query(match_stage)
            group_expr = self._json_text_expr(field)
            if fully_supported and group_expr is not None:
                statement: Select[Any] = select(group_expr.label("group_key"), func.count().label("count"))
                if predicate is not None:
                    statement = statement.where(predicate)
                statement = statement.group_by(group_expr)
                async with session_scope() as session:
                    rows = await self._load_rows(session, statement)
                docs = [
                    {"_id": row.group_key, "count": int(row.count)}
                    for row in rows
                    if row.group_key is not None
                ]
                return AggregateCursor(docs)

        docs = await self._find_docs({}, None, [], 0, None)
        for stage in pipeline:
            if "$match" in stage:
                docs = [doc for doc in docs if _matches(doc, stage["$match"])]
            elif "$group" in stage:
                group_spec = stage["$group"]
                group_field = str(group_spec.get("_id", "")).lstrip("$")
                groups: dict[str, int] = {}
                for doc in docs:
                    key = _first_value(doc, group_field)
                    if key is None:
                        continue
                    groups[str(key)] = groups.get(str(key), 0) + 1
                docs = [{"_id": key, "count": count} for key, count in groups.items()]
        return AggregateCursor(docs)

    async def _find_docs(
        self,
        query: dict[str, Any],
        projection: dict[str, Any] | None,
        sort_fields: list[tuple[str, int]],
        skip: int,
        limit: int | None,
    ) -> list[dict[str, Any]]:
        predicate = self._supported_predicate(query)
        unsupported_sort = [field for field, _ in sort_fields if self._sort_expression(field) is None]
        if unsupported_sort:
            raise ValueError(
                f"Unsupported sort fields for collection '{self.name}': {', '.join(unsupported_sort)}"
            )

        statement: Select[Any] = select(self.table.c.id, self.table.c.data)
        if predicate is not None:
            statement = statement.where(predicate)

        for field, direction in sort_fields:
            sort_expr = self._sort_expression(field)
            if sort_expr is None:
                continue
            statement = statement.order_by(sort_expr.desc() if direction < 0 else sort_expr.asc())

        if skip:
            statement = statement.offset(skip)
        if limit is not None:
            statement = statement.limit(limit)

        async with session_scope() as session:
            rows = await self._load_rows(session, statement)

        docs = [_row_to_doc(row) for row in rows]
        return [_apply_projection(doc, projection) for doc in docs]

    async def _load_rows(self, session: AsyncSession, statement: Select[Any]) -> list[Any]:
        result = await session.execute(statement)
        return list(result)

    def _compile_query(self, query: dict[str, Any]) -> tuple[ColumnElement[bool] | None, bool]:
        if not query:
            return None, True

        expressions: list[ColumnElement[bool]] = []
        fully_supported = True

        for key, expected in query.items():
            if key == "$and":
                if not isinstance(expected, list):
                    fully_supported = False
                    continue
                and_expressions: list[ColumnElement[bool]] = []
                for item in expected:
                    if not isinstance(item, dict):
                        fully_supported = False
                        continue
                    sub_expr, sub_supported = self._compile_query(item)
                    fully_supported = fully_supported and sub_supported
                    if sub_expr is not None:
                        and_expressions.append(sub_expr)
                if and_expressions:
                    expressions.append(and_(*and_expressions))
                elif expected:
                    fully_supported = False
                continue

            if key == "$or":
                if not isinstance(expected, list):
                    fully_supported = False
                    continue
                or_expressions: list[ColumnElement[bool]] = []
                for item in expected:
                    if not isinstance(item, dict):
                        fully_supported = False
                        continue
                    sub_expr, sub_supported = self._compile_query(item)
                    fully_supported = fully_supported and sub_supported
                    if sub_expr is not None:
                        or_expressions.append(sub_expr)
                if or_expressions:
                    expressions.append(or_(*or_expressions))
                elif expected:
                    fully_supported = False
                continue

            condition, condition_supported = self._compile_condition(key, expected)
            fully_supported = fully_supported and condition_supported
            if condition is not None:
                expressions.append(condition)

        if not expressions:
            return None, fully_supported
        return and_(*expressions), fully_supported

    def _supported_predicate(self, query: dict[str, Any]) -> ColumnElement[bool] | None:
        predicate, fully_supported = self._compile_query(query)
        if not fully_supported:
            raise ValueError(f"Unsupported query for collection '{self.name}'")
        return predicate

    async def _find_one_for_update(
        self,
        session: AsyncSession,
        query: dict[str, Any],
    ) -> dict[str, Any] | None:
        predicate = self._supported_predicate(query)
        statement: Select[Any] = select(self.table.c.id, self.table.c.data).limit(1).with_for_update()
        if predicate is not None:
            statement = statement.where(predicate)
        row = (await session.execute(statement)).first()
        return _row_to_doc(row) if row else None

    def _upsert_lock_key(self, query: dict[str, Any]) -> str:
        try:
            encoded = json.dumps(_serialize_json(query), sort_keys=True, separators=(",", ":"))
        except TypeError:
            encoded = str(query)
        return f"{self.name}:{encoded}"

    def _compile_condition(
        self,
        key: str,
        expected: Any,
    ) -> tuple[ColumnElement[bool] | None, bool]:
        if isinstance(expected, dict):
            if "$in" in expected:
                options = expected.get("$in")
                if not isinstance(options, list):
                    return None, False
                if not options:
                    return text("false"), True
                conditions: list[ColumnElement[bool]] = []
                fully_supported = True
                for value in options:
                    cond, supported = self._compile_equality(key, value)
                    fully_supported = fully_supported and supported
                    if cond is not None:
                        conditions.append(cond)
                if not conditions:
                    return None, False
                return or_(*conditions), fully_supported

            if "$ne" in expected:
                condition, supported = self._compile_equality(key, expected.get("$ne"))
                if condition is None:
                    return None, False
                return not_(condition), supported

            if "$regex" in expected:
                pattern = str(expected.get("$regex", ""))
                flags = str(expected.get("$options", ""))
                op = "~*" if "i" in flags else "~"
                if key == "_id":
                    return cast(self.table.c.id, String()).op(op)(pattern), True
                text_expr = self._json_text_expr(key)
                if text_expr is None:
                    return None, False
                return text_expr.op(op)(pattern), True

            return None, False

        return self._compile_equality(key, expected)

    def _compile_equality(self, key: str, value: Any) -> tuple[ColumnElement[bool] | None, bool]:
        if key == "_id":
            return self.table.c.id == _coerce_uuid(value), True

        payload = _build_contains_payload(key, value)
        if payload is None:
            return None, False
        return self.table.c.data.contains(_serialize_json(payload)), True

    def _json_text_expr(self, dotted_path: str):
        parts = [part for part in dotted_path.split(".") if part]
        if not parts:
            return None
        expr = self.table.c.data
        for part in parts:
            expr = expr[part]
        return expr.astext

    def _sort_expression(self, dotted_path: str):
        if dotted_path == "_id":
            return self.table.c.id

        text_expr = self._json_text_expr(dotted_path)
        if text_expr is None:
            return None

        if dotted_path.endswith("sort_order"):
            return cast(text_expr, Integer)

        return text_expr


async def connect_db() -> None:
    global _engine, _session_factory, _db_proxy
    if _engine is not None:
        return

    dsn = _postgres_dsn()
    _engine = create_async_engine(dsn, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    _db_proxy = DatabaseProxy()

    async with _engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(metadata.create_all)
        await _ensure_indexes(conn)


async def close_db() -> None:
    global _engine, _session_factory, _db_proxy
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    _db_proxy = None


def get_db() -> DatabaseProxy:
    if _db_proxy is None:
        raise RuntimeError("Database not connected")
    return _db_proxy


def get_collection(name: str) -> CollectionProxy:
    return CollectionProxy(name)


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not connected")
    return _session_factory


async def _ensure_indexes(conn) -> None:
    # Core uniqueness constraints
    await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users ((data->>'email'))"))
    await conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_bootstrap_marker "
            "ON users ((data->>'bootstrap_marker')) "
            "WHERE data ? 'bootstrap_marker'"
        )
    )
    await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_sessions_token ON sessions ((data->>'token'))"))
    await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_drafts_user_id ON drafts ((data->>'user_id'))"))
    await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_prompts_intent ON ai_prompts ((data->>'intent'))"))
    await conn.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_chat_history_thread_id ON ai_chat_history ((data->>'thread_id'))")
    )

    # Search/filter indexes
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sessions_expires_at ON sessions ((data->>'expires_at'))"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_profiles_type_status ON profiles ((data->>'participant_type'), (data->>'status'))"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_applications_status ON applications ((data->>'status'))"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_messages_conversation ON messages ((data->>'conversation_id'))"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_user_read ON notifications ((data->>'user_id'), (data->>'is_read'))"))

    # Full-text fallback support
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_profiles_data_trgm ON profiles USING gin ((data::text) gin_trgm_ops)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_profiles_data_gin ON profiles USING gin (data)"))

    # Vector indexes
    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_profile_vectors_metadata_gin ON profile_vectors USING gin (vector_metadata)"))
    await conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_profile_vectors_embedding "
            "ON profile_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )
    )
    await conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_ai_document_chunks_embedding "
            "ON ai_document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )
    )
    await conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_document_chunks_document_chunk "
            "ON ai_document_chunks (document_id, chunk_index)"
        )
    )
    await conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_ai_document_chunks_document_id ON ai_document_chunks (document_id)")
    )

    # Cleanup stale vector rows before enforcing referential integrity.
    await conn.execute(
        text(
            "DELETE FROM ai_document_chunks c "
            "WHERE NOT EXISTS (SELECT 1 FROM ai_documents d WHERE d.id = c.document_id)"
        )
    )
    await conn.execute(
        text(
            "DELETE FROM profile_vectors v "
            "WHERE NOT EXISTS (SELECT 1 FROM profiles p WHERE p.id = v.profile_id)"
        )
    )

    await conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_ai_document_chunks_document_id'
                ) THEN
                    ALTER TABLE ai_document_chunks
                    ADD CONSTRAINT fk_ai_document_chunks_document_id
                    FOREIGN KEY (document_id) REFERENCES ai_documents(id) ON DELETE CASCADE;
                END IF;
            END
            $$;
            """
        )
    )
    await conn.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_profile_vectors_profile_id'
                ) THEN
                    ALTER TABLE profile_vectors
                    ADD CONSTRAINT fk_profile_vectors_profile_id
                    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE;
                END IF;
            END
            $$;
            """
        )
    )


class session_scope:
    def __init__(self):
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        self._session = get_session_factory()()
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session is None:
            return
        try:
            if exc:
                await self._session.rollback()
        finally:
            await self._session.close()


def _postgres_dsn() -> str:
    if settings.postgres_dsn:
        return settings.postgres_dsn

    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


def _coerce_uuid(raw: Any) -> uuid.UUID:
    if isinstance(raw, uuid.UUID):
        return raw
    raw_text = str(raw)
    try:
        return uuid.UUID(raw_text)
    except (ValueError, TypeError, AttributeError):
        # Stable fallback allows non-UUID identifiers (for Mongo-style caller compatibility).
        return uuid.uuid5(uuid.NAMESPACE_URL, raw_text)


def _row_to_doc(row: Any) -> dict[str, Any]:
    payload = dict(row.data or {})
    payload["_id"] = str(row.id)
    return _deserialize_json(payload)


def _serialize_json(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _serialize_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_json(v) for v in value]
    return value


def _deserialize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deserialize_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deserialize_json(v) for v in value]
    return value


def _doc_from_filter(query: dict[str, Any]) -> dict[str, Any]:
    doc: dict[str, Any] = {}
    for key, value in query.items():
        if key.startswith("$"):
            continue
        if isinstance(value, dict):
            continue
        _set_path(doc, key, value)
    return doc


def _build_contains_payload(dotted_path: str, value: Any) -> dict[str, Any] | None:
    parts = [part for part in dotted_path.split(".") if part]
    if not parts:
        return None

    normalized_value = _normalize_scalar(value)
    if parts[0] == "participants" and len(parts) > 1:
        return {
            "participants": [_nested_payload(parts[1:], normalized_value)],
        }
    return _nested_payload(parts, normalized_value)


def _nested_payload(parts: list[str], value: Any) -> dict[str, Any]:
    current: Any = value
    for key in reversed(parts):
        current = {key: current}
    return current


def _apply_update(doc: dict[str, Any], update_doc: dict[str, Any], is_insert: bool) -> dict[str, Any]:
    updated = dict(doc)
    set_values = update_doc.get("$set", {})
    set_on_insert = update_doc.get("$setOnInsert", {}) if is_insert else {}

    for key, value in set_values.items():
        _set_path(updated, key, value)
    for key, value in set_on_insert.items():
        _set_path(updated, key, value)

    return updated


def _apply_projection(doc: dict[str, Any], projection: dict[str, Any] | None) -> dict[str, Any]:
    if not projection:
        return doc

    include_keys = {k for k, v in projection.items() if v}
    exclude_keys = {k for k, v in projection.items() if not v}

    if include_keys and not (len(include_keys) == 1 and "_id" in include_keys):
        projected: dict[str, Any] = {}
        if "_id" not in exclude_keys and "_id" in doc:
            projected["_id"] = doc["_id"]
        for key in include_keys:
            if key == "_id":
                continue
            value = _first_value(doc, key)
            if value is not None:
                _set_path(projected, key, value)
        return projected

    projected = dict(doc)
    for key in exclude_keys:
        _delete_path(projected, key)
    return projected


def _sort_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.lower()
    return value


def _matches(doc: dict[str, Any], query: dict[str, Any]) -> bool:
    if not query:
        return True

    for key, expected in query.items():
        if key == "$and":
            if not all(_matches(doc, item) for item in expected):
                return False
            continue

        if key == "$or":
            if not any(_matches(doc, item) for item in expected):
                return False
            continue

        values = _all_values(doc, key)

        if isinstance(expected, dict):
            if "$in" in expected:
                options = {_normalize_scalar(v) for v in expected["$in"]}
                if not any(_normalize_scalar(v) in options for v in values):
                    return False
            elif "$ne" in expected:
                wanted = _normalize_scalar(expected["$ne"])
                if any(_normalize_scalar(v) == wanted for v in values):
                    return False
            elif "$regex" in expected:
                flags = re.IGNORECASE if "i" in str(expected.get("$options", "")) else 0
                pattern = re.compile(str(expected["$regex"]), flags)
                if not any(pattern.search(str(v)) for v in values if v is not None):
                    return False
            else:
                return False
            continue

        normalized_expected = _normalize_scalar(expected)
        if not any(_normalize_scalar(v) == normalized_expected for v in values):
            return False

    return True


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _all_values(doc: Any, dotted_path: str) -> list[Any]:
    parts = dotted_path.split(".")

    def walk(current: Any, idx: int) -> list[Any]:
        if idx >= len(parts):
            return [current]
        part = parts[idx]

        if isinstance(current, list):
            values: list[Any] = []
            for item in current:
                values.extend(walk(item, idx))
            return values

        if isinstance(current, dict):
            if part in current:
                return walk(current[part], idx + 1)
            return []

        return []

    result = walk(doc, 0)
    return result or [None]


def _first_value(doc: dict[str, Any], dotted_path: str) -> Any:
    values = _all_values(doc, dotted_path)
    return values[0] if values else None


def _set_path(doc: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    current = doc
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _delete_path(doc: dict[str, Any], dotted_path: str) -> None:
    parts = dotted_path.split(".")
    current: Any = doc
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(parts[-1], None)
