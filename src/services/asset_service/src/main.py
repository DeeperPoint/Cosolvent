from fastapi import FastAPI
from src.routes.asset_service import router as asset_router

app = FastAPI()
app.include_router(asset_router)
