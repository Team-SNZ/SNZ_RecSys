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
from langchain.schema import Document
from langchain.vectorstores import FAISS

"""
환경 변수 설정: Open API key
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
벡터 DB 생성: 유저 profile의 embedding DB
"""
embedding = OpenAIEmbeddings(model="text-embedding-3-small")
vector_store = None

def _load_profile_docs_from_mongoDB(col_profile) -> list[Document]:
    """
    MongoDB에서 사용자의 profile을 읽어 Document로 변환
    """
    query = {
        "ID": {"$exists": True},
        "Profile": {"$type": "string", "$ne": ""}  # 빈 문자열 제외
    }
    projection = {"ID": 1, "Profile": 1}
    cursor = col_profile.find(query, projection)

    docs: list[Document] = []
    for doc in cursor:
        try:
            user_id = int(doc["ID"])
            user_profile = doc["Profile"]
            if not user_profile:
                continue
            docs.append(Document(page_content=user_profile, metadata={"id": user_id})) 
        except:
            continue
    return docs

def build_vector_store_from_mongo(col_profile) -> FAISS:
    docs = _load_profile_docs_from_mongoDB(col_profile)
    if not docs:
        raise RuntimeError("user_profile 컬렉션에 벡터화할 Profile이 없습니다.")
    return FAISS.from_documents(docs, embedding)

# 벡터 스토어 생성
if vector_store is None:
    vector_store = build_vector_store_from_mongo(col_profile)

"""
Multi-agent: MyState, Chatbot agent, Profiler agent, Recommender agent, spervisor agent
"""
class MyState(TypedDict, total=False):
    user_id: int
    profile: str                               # user 요약 정보
    rec_people: List[int]                      # 매칭 후보 id
    rec_travel: List[str]                      # 추천 여행지 id
    top_100_ids: List[int]                     # 100개 뽑힌 id
    
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
    feature = dict(list(feature.items())[:-1]) # 'Rec_ids' 제거 

    summary = col_summary.find_one({"ID": id})["Summary"]

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

"""
Retriever 툴 + 노드
"""
@tool("retriever", return_direct=False)
def retriever(user_id: int, profile: str, total_k=120, top_k=100) -> List[int]:
    """
    입력 프로파일과 가장 유사한 사용자 ID 상위 100개 반환(자기 자신 제외)
    total_k: 중복 고려 총 검색할 ID 개수
    top_k: 최종 검색할 ID 개수
    """
    global vector_store
    if vector_store is None:
        vector_store = build_vector_store_from_mongo(col_profile)

    results = vector_store.similarity_search(query=profile, k=total_k) # 여유 있게 뽑고 필터링
    seen = set()
    top_ids: List[int] = []
    for d in results:
        other_id = int(d.metadata.get("id"))  # 소문자 id!
        if other_id == int(user_id):
            continue
        if other_id in seen:
            continue
        seen.add(other_id)
        top_ids.append(other_id)
        if len(top_ids) == top_k:
            break
    return top_ids

def retriever_node(state: MyState) -> Command[Literal["supervisor"]]:
    print("\n---RETRIEVER---")
    user_id = state["user_id"]
    user_profile = state["profile"] 
    top_100_ids = retriever.invoke({"user_id": user_id, "profile": user_profile})
    print(len(top_100_ids))
    print(top_100_ids)

    return Command(update={"top_100_ids": top_100_ids}, 
                   goto="supervisor")

def recommender_node(state: MyState, top_k=10) -> Command[Literal["supervisor"]]:
    print("\n---RECOMMENDER---")
    
    output_parser = CommaSeparatedListOutputParser()
    format_instructions = output_parser.get_format_instructions()
    user_id = state["user_id"]
    user_profile = state["profile"] 
    top_100_ids =  state.get("top_100_ids", [])

    if not top_100_ids:
        print("top_100_ids가 비어 있습니다. retriever가 먼저 실행되어야 합니다.")
        return Command(goto="supervisor")

    # top_100_ids에 해당하는 프로필만 mongoDB에서 조회
    top_100_profiles = col_profile.find(
        {"ID": {"$in": [i for i in top_100_ids if i != user_id]}, "Profile": {"$ne": ""}},
        {"ID": 1, "Profile": 1}
    )
    
    id2prof = {doc["ID"]: doc["Profile"] for doc in top_100_profiles}
    ordered_pairs = [(i, id2prof[i]) for i in top_100_ids if i in id2prof]
    candidate_texts = "\n".join([f"user_id {i}: {p}" for i, p in ordered_pairs])

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
        rec_ids = [int(item.strip()) for item in response_list]
    except (ValueError, TypeError):
        print("파서가 유효한 숫자 목록을 반환하지 못했습니다.")
        rec_ids = []

    if rec_ids:
        rec_ids = rec_ids[:top_k]
    print(f"최종 추천된 사용자 ID: {rec_ids}")

    col_recs.update_one(
        {"ID": user_id}, 
        {"$set": {"Recs.Rec_People": rec_ids}}, 
        upsert=True
    )    
    print("\n---Rec_ids DB Update 완료---")
    
    return Command(update={"rec_people": rec_ids}, 
                   goto="supervisor")

def supervisor_node(state: MyState) -> Command[Literal["profiler", "retriever", "recommender", END]]:

    # if state.get("summary") and not state.get("profile"):
    if not state.get("profile"):
        return Command(goto="profiler")
    elif state.get("profile") and not state.get("top_100_ids"):
        return Command(goto="retriever")
    elif state.get("top_100_ids") and not state.get("rec_people"):
        return Command(goto="recommender")
    elif state.get("rec_people"):
        return Command(goto=END)
    else:
        return Command(goto="chatbot")

def create_graph():

    graph = StateGraph(MyState)
    
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("profiler", profiler_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("recommender", recommender_node)
    
    graph.add_edge(START, "supervisor")

    app = graph.compile()
    return app

if __name__ == "__main__":
    app = create_graph()

    initial_state: MyState = {
        "user_id": 1,
        "profile": "",
        "rec_people": [],
        "rec_travel": [],
        "top_100_ids": []
    }

    final_state = app.invoke(initial_state)

    