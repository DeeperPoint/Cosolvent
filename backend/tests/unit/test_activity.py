"""The market's activity record: what gets written, and who may read it."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.activity import service


@pytest.mark.asyncio
async def test_recording_an_event_never_breaks_the_caller():
    """An event describes work already done. If the write fails the work still
    happened, so the failure must not propagate into the caller's path."""
    with patch.object(service.repo, "record", new=AsyncMock(side_effect=RuntimeError("db down"))):
        await service.record("profile.updated", subject_type="profile", subject_id="p1")
    # reaching here is the assertion


@pytest.mark.asyncio
async def test_market_level_events_are_public_and_personal_ones_are_not():
    captured = {}

    async def fake_record(doc):
        captured.update(doc)
        return doc

    with patch.object(service.repo, "record", new=fake_record):
        await service.record("population.imported", subject_type="market", subject_id="GrainPlaza")
        assert captured["public"] is True

        await service.record("profile.updated", subject_type="profile", subject_id="p1")
        assert captured["public"] is False


@pytest.mark.asyncio
async def test_an_explicit_visibility_wins_over_the_default():
    captured = {}

    async def fake_record(doc):
        captured.update(doc)
        return doc

    with patch.object(service.repo, "record", new=fake_record):
        await service.record("profile.updated", public=True)
        assert captured["public"] is True


@pytest.mark.asyncio
async def test_a_system_event_is_labelled_as_such():
    captured = {}

    async def fake_record(doc):
        captured.update(doc)
        return doc

    with patch.object(service.repo, "record", new=fake_record):
        await service.record("showcase.precomputed")
        assert captured["actor_label"] == "system"


# ── repository filtering ────────────────────────────────────────────────────

class _FakeFind:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return self._docs if length is None else self._docs[:length]


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, _query):
        return _FakeFind(self._docs)


def _event(event, subject_type, subject_id, created_at, public=False):
    return {
        "event": event, "subject_type": subject_type, "subject_id": subject_id,
        "created_at": created_at, "public": public,
    }


@pytest.mark.asyncio
async def test_the_trail_of_one_profile_excludes_everyone_elses():
    from app.modules.activity import repository

    docs = [
        _event("profile.updated", "profile", "p1", "2026-10-01T10:00:00"),
        _event("profile.updated", "profile", "p2", "2026-10-01T11:00:00"),
        _event("population.imported", "market", "GrainPlaza", "2026-10-01T12:00:00", public=True),
    ]
    with patch.object(repository, "get_collection", lambda _n: _FakeCollection(docs)):
        trail = await repository.list_events(subject_type="profile", subject_id="p1")
        public = await repository.list_events(public_only=True)

    assert [e["subject_id"] for e in trail] == ["p1"]
    assert [e["event"] for e in public] == ["population.imported"]


@pytest.mark.asyncio
async def test_events_come_back_newest_first():
    from app.modules.activity import repository

    docs = [
        _event("a", "market", "m", "2026-10-01T10:00:00"),
        _event("c", "market", "m", "2026-10-03T10:00:00"),
        _event("b", "market", "m", "2026-10-02T10:00:00"),
    ]
    with patch.object(repository, "get_collection", lambda _n: _FakeCollection(docs)):
        assert [e["event"] for e in await repository.list_events()] == ["c", "b", "a"]
