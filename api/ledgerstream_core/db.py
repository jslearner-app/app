import os

from motor.motor_asyncio import AsyncIOMotorClient


def database_url() -> str:
    # DATABASE_URL for external hosting; MONGO_URL is the Emergent-managed equivalent.
    url = os.environ.get("DATABASE_URL") or os.environ.get("MONGO_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def connect():
    client = AsyncIOMotorClient(database_url())
    return client, client[os.environ["DB_NAME"]]
