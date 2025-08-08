from dotenv import load_dotenv
import matplotlib.pyplot as plt
import networkx as nx
import getpass
import os, re, sys, time, json
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


def _set_env(var: str) -> None:
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

class MyState(TypedDict, total=False):
    user_id: int
    messages: List[Dict[str, str]]            # {"role": "user|assistant", "content": "..."}
    profile: str                               # user 요약 정보
    rec_people: List[str]                      # 매칭 후보 id
    rec_travel: List[str]                      # 추천 여행지 id
    summary: str                               # Q&A 요약


load_dotenv(override=True)
_set_env("OPENAI_API_KEY")
PATH = "SNZ_RecSys/User_100.csv"
llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

QUESTION_THEMES = [
    "여행 중 최악의 경험과 그 이유",
    "여행지에서 가장 중요하게 여기는 요소",
    "같이 여행을 가고 싶은 사람의 특징",
    "이번 여행에서 가장 기대하는 것",
    "이번 여행이 자신의 삶에 어떤 의미를 남기길 바라는 점"
]

def _build_prompt(context: str, themes: List[str]) -> str:
    themes_text = "\n".join([f"- {theme}" for theme in themes])
    
    return f"""당신은 사용자의 구체적인 여행 성향을 파악하는 전문 상담가입니다.

<목표>
아래 5가지 주제에 대해 사용자의 답변을 모두 얻어야 합니다:
{themes_text}

<현재 대화 상황>
{context}

<지침>
1. 위 대화를 분석해서 어떤 주제들이 이미 다뤄졌는지 파악하세요. 
2. 대화가 없다면, "더 구체적인 당신의 여행 성향을 파악하기 위해 몇 가지 질문을 준비했습니다. 생각나는대로 편하게 답변해주세요!" 와 함께 임의로 한 가지 주제를 정해서 질문을 시작하세요.
3. 아직 다루지 않은 주제 중에서 가장 자연스럽게 이어갈 수 있는 하나를 선택하세요.
4. 사용자의 이전 답변에 공감하며 자연스럽게 다음 질문으로 넘어가세요.

상담가의 답변: """

def chatbot_node(state: MyState):
    """
    사용자와 5회에 걸쳐 여행 성향 대화를 나눈 뒤, 요약(summary)을 생성하는 노드.
    """
    print("\n---CHATBOT---")
    messages = state.get("messages", [])
    user_message_count = sum(1 for m in messages if m["role"] == "user")

    while user_message_count < 5:
        context = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        assistant_response = llm.invoke([
            {"role": "system", "content": _build_prompt(context, QUESTION_THEMES)}
        ]).content.strip()

        print(f"\nAssistant ▶ {assistant_response}")
        user_input = input("\nYou ▶ ").strip()

        if not user_input:
            print("입력이 비어 있습니다. 다시 입력해주세요.")
            continue

        messages.append({"role": "assistant", "content": assistant_response})
        messages.append({"role": "user", "content": user_input})
        user_message_count += 1

    # 5개의 user 메시지를 모두 받은 후 summary 생성
    time.sleep(2)

    # summary 생성 전 답변
    user_only = [m for m in messages if m["role"] == "user"]
    sys_prompt = (
        "다음 대화는 사용자의 여행 성향을 파악하기 위한 Q&A입니다.\n"
        "먼저 사용자의 마지막 답변에 공감하세요.\n"
        "그 후 지금까지의 사용자의 답변을 한 단락으로 누락 없이 정리한 후 최종적인 요약을 제공하세요. \n" 
        "사용자에게 추가하고 싶은 내용이 있는지 피드백을 요청하세요."
    )

    llm_input = [{"role": "system", "content": sys_prompt}] + user_only
    summary = llm.invoke(llm_input).content.strip()
    print(f"\nAssistant ▶ {summary}")
    user_input = input("\nYou ▶ ").strip()

    final_messages = [
    {"role": "assistant", "content": summary},
    {"role": "user", "content": user_input}
]
    sys_prompt = (
        "다음 대화는 사용자의 여행 성향을 파악하기 위한 Q&A입니다.\n"
        "사용자의 답변을 한 단락으로 누락 없이 정리하세요."
    )
    llm_input_final = [{"role": "system", "content": sys_prompt}] + final_messages
    final_summary = llm.invoke(llm_input_final).content.strip()
    print(f"Summary : {final_summary}")

    return Command(
        update={"messages": messages, "summary": final_summary},
    )

def create_graph():

    graph = StateGraph(MyState)
    graph.add_node("chatbot_node", chatbot_node, start=True)
    graph.add_edge(START, "chatbot_node")
    
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