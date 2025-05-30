# src/main.py
from fastapi import FastAPI
from .routes import router as api_router # Use . to indicate current package for routes
from .config.store import load_config, get_config, persist_config # Use . for config
from .config.models import AppConfig # Use . for config
from .core.logging import get_logger
from pathlib import Path
import uvicorn

logger = get_logger(__name__)

app = FastAPI(
    title="LLM Orchestration Service",
    description="An API service to orchestrate calls to various LLM providers.",
    version="0.1.0"
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting LLM Orchestration Service...")
    # Define the path to the configuration file relative to this main.py file
    # Assuming main.py is in src/ and config.json is at the root of llm-orchestration-service/
    config_file = Path(__file__).parent.parent / "config.json"
    logger.info(f"Loading configuration from: {config_file}")
    try:
        initial_config = await load_config(config_file)
        logger.info("Configuration loaded successfully.")
        # Example: Ensure a default config.json is created if it doesn't exist
        # The load_config function handles creating and persisting a default configuration if the file is missing.

    except Exception as e:
        logger.exception(f"Failed to load or create initial configuration: {e}")
        # Depending on the severity, you might want to exit or run with defaults
        # For now, we'll try to proceed, but routes might fail if config is missing.

app.include_router(api_router)

@app.get("/health", tags=["Health"])
async def health_check():
    logger.info("Health check endpoint called.")
    return {"status": "ok"}

# To run this app (from the llm-orchestration-service directory):
# uvicorn src.main:app --reload

if __name__ == "__main__":
    # This is for development purposes only, to run with `python src/main.py`
    # In production, you would use a Gunicorn or Uvicorn server directly.
    # Ensure config.json is in the parent directory (llm-orchestration-service/)
    logger.info("Running in development mode via __main__")
    uvicorn.run(app, host="0.0.0.0", port=8000)
