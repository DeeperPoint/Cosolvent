from motor.motor_asyncio import AsyncIOMotorClient
from src.core.config import Settings

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Settings.Config.MONGO_URI)
        self.db = self.client[Settings.Config.DB_NAME]
        self.assets = self.db["assets"]

db = Database()
