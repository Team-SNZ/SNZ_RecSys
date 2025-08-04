from dotenv import load_dotenv
import getpass
import os, re, sys
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
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.prebuilt import tools_condition, create_react_agent
import os
import getpass
from typing import List, Dict, Literal, TypedDict, Optional


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

LLM = ChatOpenAI(model="gpt-4o", temperature=0.3)

QUESTION_THEMES = [
    "여행 중 최악의 경험과 그 이유",
    "여행지에서 가장 중요하게 여기는 요소",
    "같이 여행을 가고 싶은 사람의 특징",
    "이번 여행에서 가장 기대하는 것",
    "여행 중 스트레스를 받는 순간"
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
2. 대화가 없다면 5가지 주제 중 임의로 하나를 선택해 대화를 시작하세요.
3. 아직 다루지 않은 주제 중에서 가장 자연스럽게 이어갈 수 있는 하나를 선택하세요.
4. 사용자의 이전 답변에 공감하며 자연스럽게 다음 질문으로 넘어가세요.

상담가의 답변: """

def chatbot_node(state: MyState) -> Command[Literal["supervisor"]]:
    messages = state.get("messages", [])
    context = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
    user_message_count = sum(1 for m in messages if m["role"] == "user")
    if user_message_count >= 5 and not state.get("summary"):
        print("Assistant ▶ 당신의 적극적인 답변 덕분에 당신의 여행 성향에 대해 보다 깊게 이해할 수 있게 되었어요! 이를 바탕으로 당신의 여행 메이트와 추천 여행지를 탐색해볼게요! ")
        sys_prompt = (
            "다음 대화는 사용자의 여행 성향을 파악하기 위한 Q&A입니다.\n"
            "사용자의 답변을 한 단락으로 누락없이 정리하세요."
        )
        
        llm_input = [{"role": "system", "content": sys_prompt}]
        for msg in messages:
            llm_input.append({"role": msg["role"], "content": msg["content"]})
                
        summary = LLM.invoke(llm_input).content.strip()
        
        return Command(
            update={"summary": summary},
            goto="supervisor",
        )

    assistant_response = LLM.invoke([
        {"role": "system", "content": _build_prompt(context, QUESTION_THEMES)}
    ]).content.strip()
    
    new_messages = messages + [
        {"role": "assistant", "content": assistant_response}
    ]
    return Command(
        update={"messages": new_messages},
        goto="supervisor",
    )


def supervisor_node(state: MyState) -> Command[Literal["chatbot", END]]:

    if state.get("summary"):
        return Command(goto=END)
    else:
        return Command(goto="chatbot")


builder = StateGraph(MyState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("chatbot", chatbot_node)
builder.add_edge(START, "supervisor")
graph = builder.compile()


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
    
    while True:
        final_state = None
        for event in graph.stream(state):
            for node_name, node_result in event.items():
                if isinstance(node_result, dict):
                    state.update(node_result)
                    final_state = state
                    if state.get("summary"):
                        break  
                    messages = state.get("messages", [])
                    if messages and messages[-1]["role"] == "assistant":
                        print("Assistant ▶", messages[-1]["content"])
                        user_text = input("\nYou ▶ ").strip()
                        if user_text:
                            state["messages"].append({"role": "user", "content": user_text})
                        break

            if state.get("summary"):
                break

        if final_state is None:
            print("오류: 상태가 업데이트되지 않았습니다.")
            break

        if state.get("summary"):
            break  
    print(f"\n=== 요약 ===\n{state['summary']}")