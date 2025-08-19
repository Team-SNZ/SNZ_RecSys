from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.agent import create_agent
from app.schemas.recommend import RecommendationRequest, RecommendationResponse


router = APIRouter(prefix="/agent", tags=["agent"])

# 백그라운드에서 실행할 스레드 풀
executor = ThreadPoolExecutor(max_workers=4)


def run_recommendation(user_id: str) -> Dict[str, Any]:
    """동기 함수로 추천 실행"""
    agent = create_agent()
    try:
        result = agent.recommend(user_id)
        return result
    finally:
        agent.close()


@router.post("/recommend", response_model=RecommendationResponse, summary="여행 동행자 및 여행지 추천")
async def recommend(request: RecommendationRequest) -> RecommendationResponse:
    """
    사용자 ID를 기반으로 여행 동행자 및 여행지를 추천합니다.
    """
    try:
        # 백그라운드에서 동기 함수 실행
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor, 
            run_recommendation, 
            request.user_id
        )
        
        return RecommendationResponse(
            user_id=request.user_id,
            rec_people=result.get("rec_people", []),
            rec_travel=result.get("rec_travel", []),
            status="success"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"추천 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/health", summary="에이전트 상태 확인")
async def health_check() -> Dict[str, str]:
    """에이전트 서비스의 상태를 확인합니다."""
    return {"status": "healthy", "service": "travel_recommendation_agent"}

