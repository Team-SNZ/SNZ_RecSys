from pydantic import BaseModel
from typing import Optional


class RecommendationRequest(BaseModel):
    user_id: str


class RecommendationResponse(BaseModel):
    user_id: str
    rec_people: list[str]
    rec_travel: list[str]
    status: str