from dotenv import load_dotenv
import matplotlib.pyplot as plt
import networkx as nx
import getpass
import os, re, sys, time, json
from typing import TypedDict, Annotated, Sequence, Literal
from operator import add as add_messages
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from typing import TypedDict, Annotated, Sequence
from operator import add as add_messages
from typing_extensions import TypedDict
from langgraph.types import Command
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.output_parsers import CommaSeparatedListOutputParser
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.prebuilt import tools_condition, create_react_agent
import os
import getpass
from typing import List, Dict, Literal, TypedDict, Optional
import pandas as pd
from pymongo import MongoClient
import sys

"""
환경 변수 설정: Open API key, CSV file path
"""
def _set_env(var: str) -> None:
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")
load_dotenv(override=True)
_set_env("OPENAI_API_KEY")

"""
MongoDB 연결
"""
client = MongoClient("mongodb+srv://sjy21ys:cjdthdtla12!@cluster0.ozrm81h.mongodb.net/")
db = client["travel_recsys"]
col_features = db["user_features"]
col_profile = db["user_profile"]
col_summary = db["user_summary"]
col_recs = db["user_recs"]

"""
Multi-agent: MyState, Chatbot agent, Profiler agent, Recommender agent, spervisor agent
"""
class MyState(TypedDict, total=False):
    user_id: int
    profile: str                               # user 요약 정보
    rec_people: List[int]                      # 매칭 후보 id
    rec_travel: List[str]                      # 추천 여행지 link
    top_100_ids: List[int]                     # retrieved user ids

llm = ChatOpenAI(model="gpt-4o", temperature=0.3)


def parse_profile_output(text: str):
    """
    LLM 응답에서 중요 요소, 피하는 요소, 요약을 파싱해서 dict로 반환
    """
    important = re.search(r"(?<=- 중요 요소:).*?(?=\n- 피하는 요소:)", text, re.DOTALL)
    avoid = re.search(r"(?<=- 피하는 요소:).*?(?=\n- 요약:)", text, re.DOTALL)
    summary = re.search(r"(?<=- 요약:).*", text, re.DOTALL)

    return {
        "important": important.group(0).strip() if important else "", # 중요 요소
        "avoid": avoid.group(0).strip() if avoid else "",             # 피하는 요소
        "summary": summary.group(0).strip() if summary else ""        # 요약
    }

def profiler_node(state: MyState) -> Command[Literal["supervisor"]]:
    '''
    해당 user_id messages와 feature를 이용하여 Profile을 생성하는 에이전트입니다. 
    '''
    
    print("\n---PROFILER---")
    id = state['user_id']
    
    feature_doc = col_features.find_one({"ID": id}) # 현재 유저id인 mondoDB에 저장된 값들 다 불러옴 -> metadata = 'ID', 'Features'
    feature = feature_doc["Features"] if feature_doc else {} 

    summary = col_summary.find_one({"ID": id})

    prompt = f"""
    당신은 여행 동반자 매칭 서비스를 위한 프로파일 생성 에이전트입니다.  
    다음은 한 사용자의 여행 성향에 대한 정형 데이터와, 사용자와의 대화 내용을 요약한 것입니다.

    - 여행 성향 피쳐:
    {feature}

    - 대화 요약:
    {summary}

    아래 형식을 따라, 사용자의 여행에서 중요하게 생각하는 요소(선호), 피하고 싶은 요소(기피), 그리고 이를 요약한 설명을 2~3문장으로 생성해주세요.  
    **가능하면 구체적인 항목(예: 기후, 동행자 성향, 활동 종류 등)을 명시해주세요.**

    <출력 형식>
    - 중요 요소:
    - 피하는 요소:
    - 요약:
    """
    
    total_profile = llm.invoke(prompt).content
    parsed = parse_profile_output(total_profile)
    print(f"profile: {parsed['summary']}")

    col_profile.update_one({"ID": id}, {"$set": {"Profile": parsed["summary"]}}, upsert=True)
    print("\n---Profile DB Update 완료---")
    
    return Command(update={"profile": parsed["summary"]}, 
                   goto= "supervisor")

#def retriever_node(state: MyState) -> Command[Literal["supervisor"]]:
    
##### 0810 Recommender tool 추가 #####
@tool
def people_rec_tool(state: MyState, top_k=10) -> Command:
    """
    기준 사용자 프로필과 top_100 후보의 프로필을 비교하여 상위 top_k명의 사용자 ID를 추천.
    결과는 DB(col_recs)에 저장하고, state.rec_people에 반영한 뒤 travel_rec_tool로 이동.
    """
    output_parser = CommaSeparatedListOutputParser()
    format_instructions = output_parser.get_format_instructions()
    user_id = state["user_id"]
    user_profile = state["profile"]
    top_100_ids = state.get("top_100_ids", [])
    if not top_100_ids:
        print("추천할 사용자 ID 목록이 없습니다.")
        return state
    
    print("\n---PEOPLE_REC_TOOL---")
    others_top_100 = list(col_profile.find({
        "ID": {"$in": top_100_ids},  # top_100_ids에 있는 사용자들만
        "Profile": {"$ne": ""}        # 프로필 비어있지 않은 사람만
    }))

    candidate_texts = "\n".join([
        f"user_id {row['ID']}: {row.get('Profile', '')}" for row in others_top_100
    ])

    prompt = f"""
당신은 여행 동행 추천 시스템입니다. 주어진 사용자 프로필과 다른 사용자 목록을 기반으로 가장 잘 맞는 동행자를 추천해야 합니다.

[기준 사용자 프로필]
{user_profile}

[비교할 다른 사용자 프로필 목록]
{candidate_texts}

[지시사항]
1. 기준 사용자와 다른 모든 사용자의 프로필을 비교하여 호환성을 분석하세요.
2. 호환성이 가장 높은 순서대로 상위 {top_k}명의 사용자 ID를 선정하세요.
3. 최종 응답은 아래 형식 지침을 반드시 따라야 합니다. 다른 설명은 절대 포함하지 마세요.

{format_instructions}

[최종 응답]
"""
    chain = llm | output_parser
    response_list = chain.invoke([HumanMessage(content=prompt)])
    
    try:
        rec_people = [int(item.strip()) for item in response_list]
    except (ValueError, TypeError):
        print("파서가 유효한 숫자 목록을 반환하지 못했습니다.")
        rec_people = []

    if rec_people:
        rec_people = rec_people[:top_k]

    print(f"최종 추천된 사용자 ID: {rec_people}")

    col_recs.update_one(
        {"ID": user_id}, 
        {"$set": {"Rec_People": rec_people}}, 
        upsert=True
    )    
    print("\n---Rec_People DB Update 완료---")
    
    return Command(update={"rec_people": rec_people}, 
                   goto="travel_rec_tool")

@tool
def travel_rec_tool(state: MyState, top_k_travel=3) -> MyState:
    """
    rec_people의 프로필과 기준 사용자 프로필을 활용해 TravelDB(100개 표본) 중 상위 top_k_travel 여행지 추천.
    결과는 DB(col_recs)에 저장하고, state.rec_travel에 반영한 뒤 종료.
    """
    output_parser = CommaSeparatedListOutputParser()
    format_instructions = output_parser.get_format_instructions()
    user_id = state["user_id"]
    user_profile = state["profile"]
    rec_people = state.get("rec_people", [])
    
    if not rec_people:
        print("추천할 사용자 ID 목록이 없습니다.")
        return state
    
    print("\n---TRAVEL_REC_TOOL---")
    others_rec_people = list(col_profile.find({
        "ID": {"$in": rec_people},  # rec_people에 있는 사용자들만
        "Profile": {"$ne": ""}       # 프로필 비어있지 않은 사람만
    }))
    if not others_rec_people:
        print("rec_people에 대한 유효한 프로필이 없습니다.")
        return Command(update={}, goto=END)
    
    rec_people_profiles = "\n".join([
        f"user_id {row['ID']}: {row.get('Profile', '')}" for row in others_rec_people
    ])

    # TravelDB에서 100개 샘플 로드 (정렬 기준은 상황에 맞게 변경 가능)
    travels = list(col_travels.find(
        {},
        {"_id": 0}  # 전체 필드 사용(코드/링크/키워드/지역 등)
    ).limit(100))

    if not travels:
        print("TravelDB에서 여행 데이터를 가져오지 못했습니다.")
        return Command(update={}, goto=END)
    
    # 여행지 목록 요약 텍스트 (LLM 입력 토큰 아끼기 위해 필요한 핵심만)
    # travel 예시 필드: {"code":"JEJU-OLLE-07","name":"올레길7코스","tags":["힐링","걷기"],"link":"..."}
    def _fmt_travel(t: Dict[str, Any]) -> str:
        code = t.get("code") or t.get("id") or t.get("link") or "UNKNOWN"
        name = t.get("name", "")
        region = t.get("region", "")
        tags = t.get("tags", [])
        tags_s = ", ".join(tags) if isinstance(tags, list) else str(tags)
        return f"{code} :: {name} :: {region} :: {tags_s}"

    travel_text = "\n".join(_fmt_travel(t) for t in travels)

    prompt = f"""
당신은 여행지 추천 시스템입니다. 기준 사용자와 그와 잘 맞을 동행자들의 프로필을 바탕으로,
아래의 여행지 후보들 중 상위 {top_k_travel}개를 골라주세요.
[기준 사용자 프로필]
{user_profile}
[비교할 다른 사용자 프로필 목록]
{rec_people_profiles}
[여행지 후보 (code :: name :: region :: tags)]
{travel_text}

[지시사항]
1. 기준 사용자와 동행자들의 공통 취향/제약을 파악하세요.
2. 후보 여행지 중 가장 적합한 상위 {top_k_travel}개를 고르세요.
3. 최종 응답은 아래 형식 지침을 반드시 따르세요. 코드(또는 링크)만 반환합니다. 설명 금지.

{format_instructions}
[최종 응답]
"""
    chain = llm | output_parser
    response_list = chain.invoke([HumanMessage(content=prompt)])
    try:
        rec_travel = [item.strip() for item in response_list if item.strip()]
    except (ValueError, TypeError):
        print("파서가 유효한 여행지 목록을 반환하지 못했습니다.")
        rec_travel = []
    if rec_travel:
        rec_travel = rec_travel[:top_k_travel]
    print(f"최종 추천된 여행지: {rec_travel}")

    try:
        col_recs.update_one(
            {"ID": user_id},
            {"$set": {"Rec_Travel": rec_travel}},
            upsert=True
        )
        print("\n---Rec_Travel DB Update 완료---")
    except Exception as e:
        print(f"Rec_Travel DB 업데이트 실패: {e}")

    return Command(update={"rec_travel": rec_travel}, goto=END)
    

def recommender_node(state: MyState) -> Command:
    """
    실행 순서 제어:
    - rec_people 없으면 -> people_rec_tool
    - rec_people 있고 rec_travel 없으면 -> travel_rec_tool
    - 둘 다 있으면 -> 종료
    """
    if not state.get("rec_people"):
        return Command(update={}, goto="people_rec_tool")
    if not state.get("rec_travel"):
        return Command(update={}, goto="travel_rec_tool")
    return Command(update={}, goto=END)

def supervisor_node(state: MyState) -> Command[Literal["profiler", "retriever", "recommender", END]]:
    # 1) 프로필이 없으면 → 프로파일러로
    if not state.get("profile"):
        return Command(goto="profiler")

    # 2) 프로필은 있는데 후보(top_100_ids)가 없으면 → 리트리버로
    if not state.get("top_100_ids"):
        return Command(goto="retriever")

    # 3) 후보는 있는데 추천이 덜 끝났으면 → 추천 파이프라인
    if not state.get("rec_people") or not state.get("rec_travel"):
        return Command(goto="recommender")

    # 4) 모두 끝나면 종료
    return Command(goto=END)


def create_graph():
    graph = StateGraph(MyState)

    # 코어 노드
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("profiler", profiler_node)
    graph.add_node("retriever", retriever_node)          # ← 새로 추가
    graph.add_node("recommender", recommender_node)

    # 추천 툴 노드 (recommender가 호출하여 이동)
    graph.add_node("people_rec_tool", people_rec_tool)
    graph.add_node("travel_rec_tool", travel_rec_tool)

    # 시작점
    graph.add_edge(START, "supervisor")

    # 안전망(edge는 각 노드의 Command(goto=...)가 주도하지만 보강 차원에서 추가)
    graph.add_edge("recommender", "people_rec_tool")
    graph.add_edge("people_rec_tool", "travel_rec_tool")
    graph.add_edge("travel_rec_tool", END)

    app = graph.compile()
    return app

if __name__ == "__main__":
    app = create_graph()

    initial_state: MyState = {
        "user_id": 1,
        "messages": [],
        "profile": "",
        "rec_people": [],
        "rec_travel": [],
        "summary": "",
    }

    final_state = app.invoke(initial_state)