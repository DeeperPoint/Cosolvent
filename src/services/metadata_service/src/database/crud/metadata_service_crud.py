from typing import Optional
from src.database.db import db
from src.database.models.metadata_service import  AssetModel
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
        return [AssetModel(asset).to_dict() for asset in assets] if assets else []
    @staticmethod
    async def add_description(asset_id: str, description: str) -> Optional[dict]:
        """
        Adds a description to an existing asset.

        :param asset_id: MongoDB ObjectId string
        :param description: Description text to add
        :returns: Updated asset data or None if not found
        """
        result = await db.assets.update_one(
            {"_id": ObjectId(asset_id)},
            {"$set": {"metadata.description": description}}
        )
        if result.modified_count > 0:
            cur =  await AssetCRUD.get_by_id(asset_id)
            return cur
        return None