import os
import getpass
from langchain.chains.summarize.refine_prompts import prompt_template
from typing import Annotated, TypedDict, List, Optional, Literal, Dict
from langgraph.graph.message import add_messages
from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from openai import max_retries
from langchain.agents import create_react_agent, AgentExecutor
from langchain.tools import tool
from langchain_openai import OpenAIEmbeddings
from typing import List, Optional
from typing_extensions import TypedDict  
from langchain.prompts import ChatPromptTemplate
import pandas as pd
from langgraph.types import Command
from dotenv import load_dotenv
import getpass
import os
import json, random
from langchain.schema import HumanMessage

# load_dotenv("/content/.env", override=True)
load_dotenv(override=True)

def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

_set_env("OPENAI_API_KEY")


class MyState(TypedDict, total=False):
    user_id: int
    messages: List[Dict[str, str]]            # {"role": "user|assistant", "content": "..."}
    profile: str                               # user 요약 정보
    rec_people: List[str]                      # 매칭 후보 id
    rec_travel: List[str]                      # 추천 여행지 id
    summary: str                               # Q&A 요약

LLM_MODEL = "gpt-4o-mini"
llm = ChatOpenAI(model=LLM_MODEL, temperature=0)

def supervisor_node(state: MyState) -> Command[Literal["recommender", END]]:

    if state.get("rec_people"):
        return Command(goto=END)
    else:
        return Command(goto="recommender")

def recommender_agent(state: MyState, top_k=10) -> Command[Literal["supervisor"]]:
    user_id = state["user_id"]
    user_profile = state["profile"]
    
    
    others = df[df['ID'] != user_id][['ID', 'Profiles']]
    
    candidate_texts = "\n".join([
        f"ID {row.ID}: {row.Profiles}" for row in others.itertuples()
    ])
    
    prompt = f"""
당신은 여행 동행 추천 에이전트입니다.

[사용자 프로필]
{user_profile}

[다른 사용자 프로필 목록]
{candidate_texts}

작업:
1. 모든 사용자를 분석하고 호환성이 가장 높은 상위 {top_k}명을 추천하세요.
2. 여행 스타일, 취향, 성격 궁합을 고려하세요.
3. 최종 결과는 JSON 배열 형식으로 사용자 ID만 반환하세요.
"""
    
    resp = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        rec_ids = json.loads(resp.content)
    except:
        rec_ids = []
    
    resp.pretty_print()
    
    return Command(update={"rec_people": resp}, 
                   goto="supervisor")

builder = StateGraph(MyState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("recommender", recommender_agent)
builder.add_edge(START, "supervisor")
builder.add_edge("supervisor", "recommender", condition=lambda state: not state.get("rec_people"))
builder.add_edge("supervisor", END, condition=lambda state: state.get("rec_people"))
builder.add_edge("recommender", "supervisor")
graph = builder.compile()
graph


if __name__ == "__main__":
    init_state: MyState = {
        "user_id": 42,
        "messages": [],
        "profile": "",
        "rec_people": [],
        "rec_travel": [],
        "summary": "",
    }
    
    state = init_state

    # Load user profile data
    df = pd.read_csv("data/user_profiles.csv")
    
    # Run the state graph
    result = graph.run(init_state)
    
    print("Final State:", result)