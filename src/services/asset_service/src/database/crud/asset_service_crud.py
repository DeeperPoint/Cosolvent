from typing import Optional
from src.database.db import db
from src.database.models.asset_service import asset_to_dict
from bson import ObjectId

class AssetCRUD:
    @staticmethod
    async def create(asset_data: dict) -> dict:
        result = await db.assets.insert_one(asset_data)
        asset_data["_id"] = result.inserted_id
        return asset_to_dict(asset_data)

    @staticmethod
    async def get_by_id(asset_id: str) -> Optional[dict]:
        asset = await db.assets.find_one({"_id": ObjectId(asset_id)})
        return asset_to_dict(asset) if asset else None
