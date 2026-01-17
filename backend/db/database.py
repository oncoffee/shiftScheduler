import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017/shift_scheduler")

_client: AsyncIOMotorClient | None = None


async def init_db():
    global _client

    from .models import EmployeeDoc, StoreDoc, ConfigDoc, ScheduleRunDoc, ComplianceRuleDoc, ComplianceAuditDoc

    _client = AsyncIOMotorClient(MONGODB_URL)
    database_name = MONGODB_URL.rsplit("/", 1)[-1].split("?")[0]
    database = _client[database_name]

    await init_beanie(
        database=database,
        document_models=[EmployeeDoc, StoreDoc, ConfigDoc, ScheduleRunDoc, ComplianceRuleDoc, ComplianceAuditDoc],
    )

    return database


def get_database():
    if _client is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    database_name = MONGODB_URL.rsplit("/", 1)[-1].split("?")[0]
    return _client[database_name]


async def close_db():
    global _client
    if _client is not None:
        _client.close()
        _client = None
