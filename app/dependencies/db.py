from fastapi import HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase


def get_db(request: Request) -> AsyncIOMotorDatabase:
    db = getattr(request.app.state, "mongo_db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return db