"""Queue helper for safely enqueueing background jobs."""

from __future__ import annotations

import logging
from typing import Any

from app.core.exceptions import ServiceUnavailableError
from app.core.redis import get_redis

logger = logging.getLogger("cosolvent.queue")


async def enqueue_job(job_name: str, *args: Any, required: bool = False) -> bool:
    """Enqueue a background job.

    If required is True and enqueueing fails, raise ServiceUnavailableError.
    """
    try:
        redis = get_redis()
        job = await redis.enqueue_job(job_name, *args)
        if job is None:
            raise RuntimeError(f"Failed to enqueue job '{job_name}'")
        return True
    except Exception as exc:
        logger.error(
            "Failed to enqueue job",
            extra={"job_name": job_name, "args_count": len(args)},
            exc_info=True,
        )
        if required:
            raise ServiceUnavailableError(
                f"Background queue unavailable for required job '{job_name}'"
            ) from exc
        return False
