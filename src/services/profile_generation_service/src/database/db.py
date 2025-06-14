from motor.motor_asyncio import AsyncIOMotorClient
from src.core.config import Settings

class Database:
    def __init__(self):
        # Initialize MongoDB client and select the database
        self.client = AsyncIOMotorClient(Settings.Config.MONGO_URI)
        self.db = self.client[Settings.Config.DB_NAME]
        # Profiles collection
        self.profiles = self.db['profiles']
        self.assets = self.db['assets']


db = Database()
