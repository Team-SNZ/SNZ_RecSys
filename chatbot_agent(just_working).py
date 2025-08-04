from dotenv import load_dotenv
import getpass
import os, re, sys, time, json
from typing import TypedDict, Annotated, Sequence, Literal, List, Dict, Optional
from operator import add as add_messages
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition, create_react_agent
from langgraph.types import Command
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from typing_extensions import TypedDict
from langchain_core.output_parsers import CommaSeparatedListOutputParser
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langgraph.prebuilt.tool_node import ToolNode
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
2. 대화가 없다면, "더 구체적인 당신의 여행 성향을 파악하기 위해 몇 가지 질문을 준비했습니다. 생각나는대로 편하게 답변해주세요!" 와 함께 임의로 한 가지 주제를 정해서 질문을 시작하세요.
3. 아직 다루지 않은 주제 중에서 가장 자연스럽게 이어갈 수 있는 하나를 선택하세요.
4. 사용자의 이전 답변에 공감하며 자연스럽게 다음 질문으로 넘어가세요.

상담가의 답변: """

def chatbot_node(state: MyState) -> MyState:
    '''
    해당 User_id의 유저와의 여행 성향 관련 대화를 생성하는 agent
    '''
    print("\n---CHATBOT---")
    messages = state.get("messages", [])
    context = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
    user_message_count = sum(1 for m in messages if m["role"] == "user")

    if user_message_count >= 5 and not state.get("summary"):
        time.sleep(2) 
        print("Assistant ▶ 당신의 적극적인 답변 덕분에 당신의 여행 성향에 대해 보다 깊게 이해할 수 있게 되었어요! 이를 바탕으로 당신의 여행 메이트와 추천 여행지를 탐색해볼게요! ")
        sys_prompt = (
            "다음 대화는 사용자의 여행 성향을 파악하기 위한 Q&A입니다.\n"
            "사용자의 답변을 한 단락으로 누락없이 정리하세요."
        )
        
        llm_input = [{"role": "system", "content": sys_prompt}]
        for msg in messages:
            llm_input.append({"role": msg["role"], "content": msg["content"]})
                
        summary = llm.invoke(llm_input).content.strip()
        
        return {"summary": summary}

    assistant_response = llm.invoke([
        {"role": "system", "content": _build_prompt(context, QUESTION_THEMES)}
    ]).content.strip()
    
    new_messages = messages + [
        {"role": "assistant", "content": assistant_response}
    ]
    return {"messages": new_messages}

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

def profiler_node(state: MyState) -> MyState:
    '''
    해당 user_id messages와 feature를 이용하여 Profile을 생성하는 에이전트입니다. 
    '''
    print("\n---PROFILER---")
    id = state['user_id']
    df = pd.read_csv(PATH)
    try:
        feature = df[df['user_id'] == id].to_dict(orient="records")[0]
    except IndexError:
        feature = {}

    summary = state['summary']

    prompt = f"""
    당신은 여행 동반자 매칭 서비스를 위한 프로파일 생성 에이전트입니다.  
    다음은 한 사용자의 여행 성향에 대한 정형 데이터와, 사용자와의 대화 내용을 요약한 것입니다.

    - 여행 성향 피쳐:
    {feature}

    - 대화 요약:
    {summary}

    아래 형식을 따라, 사용자의 여행에서 중요하게 생각하는 요소(선호), 피하고 싶은 요소(기피), 그리고 이를 요약한 설명을 생성해주세요.  
    **가능하면 구체적인 항목(예: 기후, 동행자 성향, 활동 종류 등)을 명시해주세요.**

    <출력 형식>
    - 중요 요소:
    - 피하는 요소:
    - 요약:
    """

    total_profile = llm.invoke(prompt).content
    parsed = parse_profile_output(total_profile)
    print(f"profile : {parsed['summary']}")
    df.loc[df['user_id'] == id, "profile"] = parsed["summary"]
    df.to_csv(PATH, index=False)

    return {"profile": parsed["summary"]}


def recommender_node(state: MyState, top_k=3) -> MyState:
    print("\n---RECOMMENDER---")
    
    output_parser = CommaSeparatedListOutputParser()
    format_instructions = output_parser.get_format_instructions()
    
    user_id = state["user_id"]
    user_profile = state["profile"]
    df = pd.read_csv(PATH)
    others = df[(df['user_id'] != user_id) & (df['profile'].notna())][['user_id', 'profile']]
    
    candidate_texts = "\n".join([
        f"user_id {row.user_id}: {row.profile}" for row in others.itertuples()
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
    # print(response_list)
    try:
        rec_ids = [int(item.strip()) for item in response_list]
    except (ValueError, TypeError):
        print("파서가 유효한 숫자 목록을 반환하지 못했습니다.")
        rec_ids = []

    # print(f"Output Parser로 추출한 ID 목록: {rec_ids}")

    if rec_ids:
        rec_ids = rec_ids[:top_k]

    print(f"최종 추천된 사용자 ID: {rec_ids}")

    if "rec_ids" not in df.columns:
        df["rec_ids"] = pd.Series(dtype='object')
    
    df.loc[df['user_id'] == user_id, "rec_ids"] = str(rec_ids)
    df.to_csv(PATH, index=False)
    
    return {"rec_people": rec_ids}


def supervisor_node(state: MyState) -> str:
    if state.get("summary") and not state.get("profile"):
        return "profiler"
    elif state.get("profile") and not state.get("rec_people"):
        return "recommender"
    elif state.get("rec_people"):
        return END
    else:
        return "chatbot"


if __name__ == "__main__":
    builder = StateGraph(MyState)

    builder.add_node("chatbot", chatbot_node)
    builder.add_node("profiler", profiler_node)
    builder.add_node("recommender", recommender_node)
    
    builder.set_entry_point("chatbot")

    builder.add_edge("profiler", "recommender")
    builder.add_edge("recommender", END)
    
    def after_chatbot_condition(state: MyState) -> str:
        if state.get("summary"):
            return "profiler"
        else:
            return END

    builder.add_conditional_edges(
        "chatbot",
        after_chatbot_condition,
        {"profiler": "profiler", END: END}
    )

    app = builder.compile()


    initial_state: MyState = {
        "user_id": 1,
        "messages": [],
    } 
    
    current_state = initial_state
    
    while True:
        result = app.invoke(current_state)

        if result.get('messages') and (not current_state.get('messages') or len(result['messages']) > len(current_state['messages'])):
            last_message = result['messages'][-1]['content']
            print(f"Assistant ▶ {last_message}")

        if result.get('rec_people'):
            print("\n--- 최종 추천 결과 ---")
            print(f"당신과 잘 맞는 여행 메이트 후보: {result['rec_people']}")
            break
        
        user_input = input("You ▶ ")
        if user_input.lower() in ["exit", "quit"]:
            print("대화를 종료합니다.")
            break
        
        current_state = result.copy()
        current_state['messages'] = current_state.get('messages', []) + [{"role": "user", "content": user_input}]