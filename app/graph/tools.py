from langchain_core.tools import tool
from typing import List, Dict, Any
from langgraph.types import Command
from langgraph.graph import END
from langchain_core.output_parsers import CommaSeparatedListOutputParser
from langchain_core.messages import HumanMessage
import logging

from app.graph.state import MyState
from app.services.vectorstore import get_vector_store_manager
from app.prompts.recommender_prompts import (
    create_people_recommendation_prompt_template,
    create_travel_recommendation_prompt_template,
    format_candidate_profiles,
    format_travel_candidates
)
from app.core.config import get_settings

# Logger 설정
logger = logging.getLogger(__name__)

"""
Retriever 툴 + 노드
"""
@tool("retriever", return_direct=False)
def retriever(user_id: str, profile: str, col_profile=None) -> List[str]:
    """
    입력 프로파일과 가장 유사한 사용자 ID 상위 k개 반환(자기 자신 제외)
    """
    settings = get_settings()
    vector_manager = get_vector_store_manager()
    
    # 벡터스토어가 없으면 빌드
    if vector_manager._vector_store is None:
        if col_profile is None:
            raise ValueError("벡터스토어와 col_profile이 모두 없습니다.")
        vector_manager.load_or_build_vector_store(col_profile)
    
    vector_store = vector_manager.vector_store
    results = vector_store.similarity_search(query=profile, k=settings.retrieval_total_k)
    
    seen = set()
    top_ids: List[str] = []
    for d in results:
        other_id = str(d.metadata.get("id"))  # 방어적 캐스팅
        if other_id == str(user_id):
            continue
        if other_id in seen:
            continue
        seen.add(other_id)
        top_ids.append(other_id)
        if len(top_ids) == settings.retrieval_top_k:
            break
    return top_ids


"""
동반자, 여행지 추천 툴 + 노드
"""
def people_rec_tool(state: MyState, collections: Dict, llm) -> Command:
    """
    기준 사용자 프로필과 top_100 후보의 프로필을 비교하여 상위 top_k명의 사용자 ID를 추천.
    결과는 DB(col_recs)에 저장하고, state.rec_people에 반영한 뒤 travel_rec_tool로 이동.
    """
    settings = get_settings()
    top_k = settings.people_rec_top_k
    
    output_parser = CommaSeparatedListOutputParser()
    format_instructions = output_parser.get_format_instructions()
    
    user_id = state["user_id"]
    user_profile = state["profile"]
    top_100_ids = state.get("top_100_ids", [])
    
    if not top_100_ids:
        logger.warning("추천할 사용자 ID 목록이 없습니다.")
        return Command(update={}, goto="supervisor")
    
    logger.info("---PEOPLE_REC_TOOL---")
    
    # MongoDB에서 프로필 조회
    col_profile = collections["col_profile"]
    top_100_profiles = col_profile.find(
        {"ID": {"$in": [i for i in top_100_ids if i != user_id]}, "Profile": {"$ne": ""}},
        {"ID": 1, "Profile": 1}
    )
    
    id2prof = {doc["ID"]: doc["Profile"] for doc in top_100_profiles}
    ordered_pairs = [(i, id2prof[i]) for i in top_100_ids if i in id2prof]
    
    # 프롬프트 템플릿 사용
    prompt_template = create_people_recommendation_prompt_template()
    candidate_profiles = format_candidate_profiles(ordered_pairs)
    
    prompt = prompt_template.format(
        user_profile=user_profile,
        candidate_profiles=candidate_profiles,
        top_k=top_k,
        format_instructions=format_instructions
    )
    
    chain = llm | output_parser
    response_list = chain.invoke([HumanMessage(content=prompt)])
    
    try:
        rec_people = [str(item).strip() for item in response_list if str(item).strip()]
        rec_people = rec_people[:top_k]
    except (ValueError, TypeError):
        logger.error("파서가 유효한 추천 목록을 반환하지 못했습니다.")
        rec_people = []

    logger.info(f"최종 추천된 사용자 ID: {rec_people}")

    # DB 업데이트
    col_recs = collections["col_recs"]
    col_recs.update_one(
        {"ID": user_id}, 
        {"$set": {"Recs.Rec_People": rec_people}}, 
        upsert=True
    )    
    logger.info("---Rec_People DB Update 완료---")
    
    return Command(update={"rec_people": rec_people}, 
                   goto="supervisor")


def travel_rec_tool(state: MyState, collections: Dict, llm) -> Command:
    """
    rec_people의 프로필(10명)과 기준 사용자 프로필을 활용해 TravelDB(80개 표본) 중 상위 top_k_travel 여행지 추천.
    결과는 DB(col_recs)에 저장하고, state.rec_travel에 반영한 뒤 종료.
    """
    settings = get_settings()
    top_k_travel = settings.travel_rec_top_k
    
    output_parser = CommaSeparatedListOutputParser()
    format_instructions = output_parser.get_format_instructions()

    user_id = state["user_id"]
    user_profile = state["profile"]
    rec_people = state.get("rec_people", [])
    
    if not rec_people:
        logger.warning("추천할 사용자 ID 목록이 없습니다.")
        return Command(update={}, goto=END)
    
    logger.info("---TRAVEL_REC_TOOL---")

    # 동행자 프로필 조회
    col_profile = collections["col_profile"]
    others_rec_people = list(col_profile.find(
        {"ID": {"$in": rec_people}, "Profile": {"$ne": ""}},
        {"ID": 1, "Profile": 1}
    ))

    if not others_rec_people:
        logger.warning("rec_people에 대한 유효한 프로필이 없습니다.")
        return Command(update={}, goto=END)
    
    rec_people_profiles = "\n".join([
        f"user_id {row['ID']}: {row.get('Profile', '')}" for row in others_rec_people
    ])

    # TravelDB에서 80개 후보 로드
    travel_info = collections["travel_info"]
    travels: List[Dict[str, Any]] = list(
        travel_info.find(
            {},
            {"product_code": 1, "title": 1, "price": 1,
             "hashtags": 1, "features": 1, "description": 1}
        ).limit(80)
    )

    if not travels:
        logger.error("TravelDB에서 여행 데이터를 가져오지 못했습니다.")
        return Command(update={}, goto=END)

    # 프롬프트 템플릿 사용
    prompt_template = create_travel_recommendation_prompt_template()
    travel_candidates = format_travel_candidates(travels)
    
    prompt = prompt_template.format(
        user_profile=user_profile,
        rec_people_profiles=rec_people_profiles,
        travel_candidates=travel_candidates,
        top_k_travel=top_k_travel,
        format_instructions=format_instructions
    )
    
    chain = llm | output_parser
    response_list = chain.invoke([HumanMessage(content=prompt)])
    
    try:
        rec_travel = [item.strip() for item in response_list if item.strip()]
        rec_travel = rec_travel[:top_k_travel]
    except (ValueError, TypeError):
        logger.error("파서가 유효한 여행지 목록을 반환하지 못했습니다.")
        rec_travel = []
        
    logger.info(f"최종 추천된 여행지: {rec_travel}")

    # DB 업데이트
    try:
        col_recs = collections["col_recs"]
        col_recs.update_one(
            {"ID": user_id},
            {"$set": {"Recs.Rec_Travel": rec_travel}}, 
            upsert=True
        )
        logger.info("---Rec_Travel DB Update 완료---")
    except Exception as e:
        logger.error(f"Rec_Travel DB 업데이트 실패: {e}")

    return Command(update={"rec_travel": rec_travel}, goto=END)