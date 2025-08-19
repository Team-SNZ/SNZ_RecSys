from langchain_core.prompts import PromptTemplate
from typing import List, Dict, Any


def create_people_recommendation_prompt_template() -> PromptTemplate:
    """
    동행자 추천을 위한 프롬프트 템플릿
    """
    template = """당신은 여행 동행 추천 시스템입니다. 주어진 사용자 프로필과 다른 사용자 목록을 기반으로 가장 잘 맞는 동행자를 추천해야 합니다.

    [기준 사용자 프로필]
    {user_profile}

    [비교할 다른 사용자 프로필 목록]
    {candidate_profiles}

    [지시사항]
    1. 기준 사용자와 다른 모든 사용자의 프로필을 비교하여 호환성을 분석하세요.
    2. 호환성이 가장 높은 순서대로 상위 {top_k}명의 사용자 ID를 선정하세요.
    3. 최종 응답은 아래 형식 지침을 반드시 따라야 합니다. 다른 설명은 절대 포함하지 마세요.

    {format_instructions}

    [최종 응답]
    """
    
    return PromptTemplate(
        input_variables=["user_profile", "candidate_profiles", "top_k", "format_instructions"],
        template=template
    )


def create_travel_recommendation_prompt_template() -> PromptTemplate:
    """
    여행지 추천을 위한 프롬프트 템플릿
    """
    template = """당신은 여행지 추천 시스템입니다. 기준 사용자와 그와 잘 맞을 동행자들의 프로필을 바탕으로,
아래의 여행지 후보들 중 상위 {top_k_travel}개를 골라주세요.

[기준 사용자 프로필]
{user_profile}

[비교할 다른 사용자 프로필 목록]
{rec_people_profiles}

[여행지 후보 (code :: name :: region :: tags)]
{travel_candidates}

[지시사항]
1. 기준 사용자와 동행자들의 공통 취향/제약을 파악하세요.
2. 후보 여행지 중 가장 적합한 상위 {top_k_travel}개를 고르세요.
3. 최종 응답은 아래 형식 지침을 반드시 따르세요. 코드(또는 링크)만 반환합니다. 설명 금지.

{format_instructions}

[최종 응답]"""
    
    return PromptTemplate(
        input_variables=["user_profile", "rec_people_profiles", "travel_candidates", "top_k_travel", "format_instructions"],
        template=template
    )


def format_candidate_profiles(candidates: List[tuple[str, str]]) -> str:
    """
    후보자 프로필 리스트를 프롬프트용 문자열로 포맷팅
    """
    return "\n".join([f"user_id {user_id}: {profile}" for user_id, profile in candidates])


def format_travel_data(travel: Dict[str, Any]) -> str:
    """
    여행 데이터를 프롬프트용 문자열로 포맷팅
    """
    def _safe_list(x):
        if x is None:
            return []
        if isinstance(x, list):
            return x
        try:
            return [s.strip() for s in str(x).split(",") if s.strip()]
        except Exception:
            return []
    
    code = travel.get("product_code", "UNKNOWN")
    title = travel.get("title", "")
    price = travel.get("price", "")
    tags = _safe_list(travel.get("hashtags")) + _safe_list(travel.get("features"))
    tags_s = ", ".join(tags) if tags else ""
    
    return f"{code} :: {title} :: {price} :: {tags_s}"


def format_travel_candidates(travels: List[Dict[str, Any]]) -> str:
    """
    여행 후보들을 프롬프트용 문자열로 포맷팅
    """
    return "\n".join([format_travel_data(travel) for travel in travels])
