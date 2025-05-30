from motor.motor_asyncio import AsyncIOMotorClient
from src.core.config import Config

class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGO_URI)
        self.db = self.client[Config.DB_NAME]
        self.assets = self.db["assets"]

db = Database()
