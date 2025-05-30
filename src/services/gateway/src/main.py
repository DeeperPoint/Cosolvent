from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from routes.gateway import router as gateway_router

app = FastAPI(title="API Gateway")

# Enable CORS for all origins and key methods
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

# Mount the gateway proxy under /api
app.include_router(gateway_router, prefix="/api")