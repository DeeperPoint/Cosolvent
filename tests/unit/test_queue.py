"""Tests for queue enqueue wrapper."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ServiceUnavailableError
from app.core.queue import enqueue_job


@pytest.mark.asyncio
async def test_enqueue_job_success():
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(return_value={"job_id": "123"})
    with patch("app.core.queue.get_redis", return_value=mock_redis):
        ok = await enqueue_job("job.name", "a", 1)
    assert ok is True


@pytest.mark.asyncio
async def test_enqueue_job_optional_failure_returns_false():
    with patch("app.core.queue.get_redis", side_effect=RuntimeError("down")):
        ok = await enqueue_job("job.name", required=False)
    assert ok is False


@pytest.mark.asyncio
async def test_enqueue_job_required_failure_raises():
    with patch("app.core.queue.get_redis", side_effect=RuntimeError("down")):
        with pytest.raises(ServiceUnavailableError):
            await enqueue_job("job.name", required=True)
