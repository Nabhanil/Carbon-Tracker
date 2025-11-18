# src/db.py
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()  # loads .env from project root

MONGO_URI = os.getenv("MONGO_URI")
DBNAME = os.getenv("MONGO_DBNAME", "carbonwise_python")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI not set in .env")

# Fail fast in dev if Atlas isn't reachable (tunable)
client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DBNAME]

# Collections used by the app
users_coll = db["users"]
vehicles_coll = db["vehicles"]
gps_coll = db["gps_logs"]
emissions_coll = db["emissions"]

# Helper functions
async def ping_db() -> bool:
    """
    Ping the MongoDB server. Returns True if reachable, False otherwise.
    Call this in your startup event to detect connection problems early.
    """
    try:
        # motor exposes .command on database objects
        await db.command("ping")
        return True
    except Exception as e:
        # log the error in a real app (here we print for simplicity)
        print("MongoDB ping failed:", e)
        return False

def close_client():
    """Close the underlying motor client (useful in tests or shutdown)."""
    try:
        client.close()
    except Exception:
        pass
