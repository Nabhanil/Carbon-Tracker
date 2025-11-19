import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load .env specifically from this folder
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DBNAME", "food_emissions_db")

_client = AsyncIOMotorClient(MONGO_URI)
db = _client[DB_NAME]
