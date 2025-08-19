from langgraph.types import Command
from langgraph.graph import END
from typing import Literal, Dict
import logging

from app.graph.state import MyState
from app.graph.tools import retriever, people_rec_tool, travel_rec_tool
from app.utils.profile_parser import parse_profile_output
from app.prompts.profiler_prompts import create_profile_prompt_template, format_features_for_prompt
from app.core.config import get_settings

# Logger 설정
logger = logging.getLogger(__name__)


def retriever_node(state: MyState, collections: Dict) -> Command[Literal["supervisor"]]:
    logger.info("---RETRIEVER---")
    user_id = state["user_id"]
    user_profile = state["profile"] 
    
    col_profile = collections["col_profile"]
    top_100_ids = retriever.invoke({
        "user_id": user_id, 
        "profile": user_profile, 
        "col_profile": col_profile
    })
    logger.info(f"검색된 유사 사용자 수: {len(top_100_ids)}")
    logger.info(f"상위 10개: {top_100_ids[:10]}")

    return Command(update={"top_100_ids": top_100_ids}, 
                   goto="supervisor")

def profiler_node(state: MyState, collections: Dict, llm) -> Command[Literal["supervisor"]]:
    """
    해당 user_id messages와 feature를 이용하여 Profile을 생성하는 에이전트입니다. 
    """
    logger.info("---PROFILER---")
    user_id = state['user_id']
    
    # MongoDB에서 데이터 조회
    col_features = collections["col_features"]
    col_summary = collections["col_summary"]
    col_profile = collections["col_profile"]
    
    feature_doc = col_features.find_one({"ID": user_id})
    feature = feature_doc["Features"] if feature_doc else {}
    
    summary_doc = col_summary.find_one({"ID": user_id})
    summary = summary_doc["Summary"] if summary_doc else ""
    
    # 핵심 여행 정보 키
    important_keys = [
        "여행일정강도", "국내or해외", "산or바다", "랜드마크", 
        "여행희망지역", "싫어하는기후", "여행목적", "숙소유형", "여행예산"
    ]

    # 필수 속성 추출 (없으면 빈값)
    important_features = {k: feature.get(k, "") for k in important_keys}
    
    # 프롬프트 템플릿 사용
    prompt_template = create_profile_prompt_template()
    important_str, all_str = format_features_for_prompt(important_features, feature)
    
    prompt = prompt_template.format(
        important_features=important_str,
        all_features=all_str,
        summary=summary
    )
    
    total_profile = llm.invoke(prompt).content
    parsed = parse_profile_output(total_profile)
    logger.info(f"생성된 프로필: {parsed['summary']}")

    # DB 업데이트
    col_profile.update_one(
        {"ID": user_id}, 
        {"$set": {"Profile": parsed["summary"]}}, 
        upsert=True
    )
    logger.info("---Profile DB Update 완료---")
    
    return Command(update={"profile": parsed["summary"]}, 
                   goto="supervisor")


def recommender_node(state: MyState, collections: Dict, llm) -> Command:
    """
    실행 순서 제어:
    - rec_people 없으면 -> people_rec_tool
    - rec_people 있고 rec_travel 없으면 -> travel_rec_tool
    - 둘 다 있으면 -> 종료
    """
    logger.info("---RECOMMENDER_NODE---")
    logger.info(f"현재 상태 - rec_people: {len(state.get('rec_people', []))}, rec_travel: {len(state.get('rec_travel', []))}")
    
    if not state.get("rec_people"):
        logger.info("rec_people가 없음 -> people_rec_tool 실행")
        return people_rec_tool(state, collections, llm)
    if not state.get("rec_travel"):
        logger.info("rec_travel이 없음 -> travel_rec_tool 실행")
        return travel_rec_tool(state, collections, llm)
    
    logger.info("추천 완료 -> 종료")
    return Command(update={}, goto=END)


def supervisor_node(state: MyState) -> Command[Literal["profiler", "retriever", "recommender", END]]:
    logger.info("---SUPERVISOR_NODE---")
    
    # 1) 프로필 없으면 → 프로파일러
    if not state.get("profile"):
        logger.info("profile이 없음 -> profiler로 이동")
        return Command(goto="profiler")

    # 2) 후보 id 없으면 → 리트리버
    if not state.get("top_100_ids"):
        logger.info("top_100_ids가 없음 -> retriever로 이동")
        return Command(goto="retriever")

    # 3) 동행 추천/여행 추천 중 하나라도 비어 있으면 → 추천 파이프라인
    if not state.get("rec_people") or not state.get("rec_travel"):
        logger.info(f"추천 미완성 (people: {len(state.get('rec_people', []))}, travel: {len(state.get('rec_travel', []))}) -> recommender로 이동")
        return Command(goto="recommender")

    # 4) 모두 끝났으면 종료
    logger.info("모든 추천 완료 -> 종료")
    return Command(goto=END)