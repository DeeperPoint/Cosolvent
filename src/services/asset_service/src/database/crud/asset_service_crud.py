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
    @staticmethod
    async def get_by_user_id(user_id: str) -> list[dict]:
        assets = await db.assets.find({"user_id": user_id}).to_list(length=None)
        return [asset_to_dict(asset) for asset in assets] if assets else []
    @staticmethod
    async def update_metadata(asset_id: str, metadata: dict) -> dict | None:
        """
        Update the metadata fields (e.g., description, status) for a given asset.
        Returns the updated asset dict or None if not found.
        """
        result = await db.assets.update_one(
            {"_id": ObjectId(asset_id)},
            {"$set": metadata}
        )
        if result.matched_count == 0:
            return None
        asset = await db.assets.find_one({"_id": ObjectId(asset_id)})
        return asset_to_dict(asset) if asset else None
