from typing import Optional
from src.database.db import db
from src.database.models.profile_generation_service import  FarmerProfileModel
from src.database.models.metadata_model import AssetModel
from bson import ObjectId


class PROFILECRUD:
    @staticmethod
    async def get_by_id(profile_id: str) -> Optional[dict]:
        profile = await db.profiles.find_one({"_id": ObjectId(profile_id)})
        return FarmerProfileModel(profile).to_dict() if profile else None
    @staticmethod
    async def create(profile_data: dict) -> dict:
        result = await db.profiles.insert_one(profile_data)
        profile_data["_id"] = result.inserted_id
        return FarmerProfileModel(profile_data)
    @staticmethod
    async def get_metadata_by_asset_id(asset_id: str) -> Optional[dict]:
        asset = await db.assets.find_one({"_id": ObjectId(asset_id)})
        print(asset)
        cur_asset =  AssetModel(asset).to_dict() if asset else None
        return cur_asset['metadata'] if cur_asset else None

