"""Custom exceptions and FastAPI exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found"):
        super().__init__(message, 404)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, 403)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, 401)


class TooManyRequestsError(AppError):
    def __init__(self, message: str = "Too many requests", retry_after: int | None = None):
        super().__init__(message, 429)
        self.retry_after = retry_after


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict"):
        super().__init__(message, 409)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str = "Service unavailable"):
        super().__init__(message, 503)


class ConfigError(Exception):
    """Raised when marketplace config is invalid."""


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        # Retry-After tells a well-behaved client when to come back instead of
        # hammering a throttled endpoint (RFC 9110 §10.2.3).
        headers = None
        retry_after = getattr(exc, "retry_after", None)
        if retry_after:
            headers = {"Retry-After": str(int(retry_after))}
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
            headers=headers,
        )
