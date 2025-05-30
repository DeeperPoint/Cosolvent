# core/logging.py
import logging
import sys
from fastapi import Request

# Configure basic logging
# In a production environment, you might want to use a more sophisticated logging setup,
# e.g., logging to a file, using a logging service, or structured logging (JSON).

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log to stdout
    ]
)

def get_logger(name: str):
    """Returns a logger instance with the given name."""
    return logging.getLogger(name)

# Example of request-scoped logging (conceptual)
# Actual implementation might involve middleware to inject a request ID

async def log_request_info(request: Request):
    logger = get_logger("request_logger")
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    # You could add more details like headers, client IP, etc.

# Example usage in an endpoint:
# from .logging import get_logger, log_request_info
# logger = get_logger(__name__)
# @router.post("/some_endpoint")
# async def some_endpoint(request: Request, ...):
#     await log_request_info(request)
#     logger.info("Processing endpoint logic...")
#     ...
