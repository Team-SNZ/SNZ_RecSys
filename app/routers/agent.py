from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.dependencies.db import get_db


router = APIRouter(prefix="/agent", tags=["agent"])

@router.get("", response_model=dict, summary="Agent 컬렉션에 새 데이터 등록")
async def get_route(
    payload: dict,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    return {"id": "123"}

@router.post("", response_model=dict, summary="Agent 컬렉션에 새 데이터 등록")
async def create_route(
    payload: dict,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, str]:
    return {"id": "123"}

