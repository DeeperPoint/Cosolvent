from typing import Optional
from src.database.db import db
from src.database.models.asset_service import  AssetModel
from bson import ObjectId

class AssetCRUD:
    @staticmethod
    async def create(asset_data: dict) -> dict:
        result = await db.assets.insert_one(asset_data)
        asset_data["_id"] = result.inserted_id
        return AssetModel(asset_data).to_dict()

    @staticmethod
    async def get_by_id(asset_id: str) -> Optional[dict]:
        asset = await db.assets.find_one({"_id": ObjectId(asset_id)})
        return AssetModel(asset).to_dict() if asset else None
    @staticmethod
    async def get_by_user_id(user_id: str) -> list[dict]:
        assets = await db.assets.find({"user_id": user_id}).to_list(length=None)
        return [AssetModel(assets).to_dict() for asset in assets] if assets else []
