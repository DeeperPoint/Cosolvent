from __future__ import annotations

import pytest

from app.core.redis import parse_redis_settings
from app.workers import settings as worker_settings


def test_parse_redis_settings_supports_auth_and_db_suffix():
    parsed = parse_redis_settings("redis://:secret@redis.example.com:6380/2")
    assert parsed.host == "redis.example.com"
    assert parsed.port == 6380
    assert parsed.password == "secret"
    assert parsed.database == 2
    assert parsed.ssl is False


def test_parse_redis_settings_supports_rediss_username_password():
    parsed = parse_redis_settings("rediss://svc:secret@cache.example.com:6381/5")
    assert parsed.host == "cache.example.com"
    assert parsed.port == 6381
    assert parsed.username == "svc"
    assert parsed.password == "secret"
    assert parsed.database == 5
    assert parsed.ssl is True


def test_parse_redis_settings_accepts_host_port_without_scheme():
    parsed = parse_redis_settings("localhost:6379")
    assert parsed.host == "localhost"
    assert parsed.port == 6379
    assert parsed.database == 0


def test_parse_redis_settings_rejects_unsupported_scheme():
    with pytest.raises(ValueError):
        parse_redis_settings("http://localhost:6379")


def test_worker_parser_reuses_shared_redis_parser(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(worker_settings.settings, "redis_url", "redis://:pw@worker-redis:6390/7")
    parsed = worker_settings._parse_redis_settings()
    assert parsed.host == "worker-redis"
    assert parsed.port == 6390
    assert parsed.password == "pw"
    assert parsed.database == 7
