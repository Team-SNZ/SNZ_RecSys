from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from fastapi import Depends
from .db import get_db


def get_user_features_collection(db: AsyncIOMotorDatabase = Depends(get_db)) -> AsyncIOMotorCollection:
    """사용자 피쳐 컬렉션 의존성"""
    return db["user_features"]


def get_user_profile_collection(db: AsyncIOMotorDatabase = Depends(get_db)) -> AsyncIOMotorCollection:
    """사용자 프로필 컬렉션 의존성"""
    return db["user_profile"]


def get_user_summary_collection(db: AsyncIOMotorDatabase = Depends(get_db)) -> AsyncIOMotorCollection:
    """사용자 요약 컬렉션 의존성"""
    return db["user_summary"]


def get_user_recs_collection(db: AsyncIOMotorDatabase = Depends(get_db)) -> AsyncIOMotorCollection:
    """사용자 추천 컬렉션 의존성"""
    return db["user_recs"]


def get_travel_info_collection(db: AsyncIOMotorDatabase = Depends(get_db)) -> AsyncIOMotorCollection:
    """여행 정보 컬렉션 의존성"""
    return db["travel_info"]


# 동기 버전 (LangGraph 노드에서 사용)
def get_sync_collections(db):
    """
    동기 MongoDB 클라이언트를 위한 컬렉션 반환 함수
    LangGraph 노드에서 사용하기 위함
    """
    return {
        "col_features": db["user_features"],
        "col_profile": db["user_profile"], 
        "col_summary": db["user_summary"],
        "col_recs": db["user_recs"],
        "travel_info": db["travel_info"]
    }
