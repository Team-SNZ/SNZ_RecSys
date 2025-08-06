import uuid, time, re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Literal
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import uuid
import os
import getpass

def _set_env(var: str) -> None:
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")

load_dotenv(override=True)
_set_env("OPENAI_API_KEY")

llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

QUESTION_THEMES = [
    "여행 중 최악의 경험과 그 이유",
    "여행지에서 가장 중요하게 여기는 요소",
    "같이 여행을 가고 싶은 사람의 특징",
    "이번 여행에서 가장 기대하는 것",
    "여행 중 스트레스를 받는 순간"
]

def build_prompt(context: str, themes: List[str]) -> str:
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

# 실제 서비스라면 → Redis / DB
sessions: Dict[str, Dict] = {}

class StartRequest(BaseModel):
    user_id: int

class ReplyRequest(BaseModel):
    message: str  
    session_id: str

class ChatResponse(BaseModel):
    session_id: str | None = None
    assistant: str
    finished: bool                
    summary: str | None = None  

# ---------- FastAPI ----------
app = FastAPI()

@app.post("/chat/start", response_model=ChatResponse)
def start_chat(req: StartRequest):
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "user_id": req.user_id,
        "messages": [],       # {"role": "assistant|user", "content": "..."}
        "count": 0,           # user message 수
        "summary": None
    }
    # 첫 질문 생성
    assistant = _next_question(sessions[session_id])
    return ChatResponse(session_id=session_id, assistant=assistant, finished=False)

@app.post("/chat/reply", response_model=ChatResponse)
def user_reply(req: ReplyRequest):
    session_id = req.session_id
    if session_id not in sessions:
        raise HTTPException(404, "There is no session.")

    st = sessions[session_id]
    st["messages"].append({"role": "user", "content": req.message})
    st["count"] += 1

    if st["count"] >= 5 and st["summary"] is None:
        st["summary"] = _make_summary(st)
        assistant_text = (
            "당신의 적극적인 답변 덕분에 여행 성향을 보다 깊이 이해할 수 있게 되었어요!\n"
            "이를 바탕으로 당신의 여행 메이트와 추천 여행지를 탐색해볼게요!"
        )
        return ChatResponse(session_id=session_id, assistant=assistant_text, finished=True, summary=st["summary"])

    assistant = _next_question(st)
    return ChatResponse(assistant=assistant, finished=False)

def _next_question(state: Dict) -> str:
    ctx = "\n".join([f"{m['role']}: {m['content']}" for m in state["messages"]])
    assistant = llm.invoke([{"role": "system", "content": build_prompt(ctx, QUESTION_THEMES)}]).content.strip()
    state["messages"].append({"role": "assistant", "content": assistant})
    return assistant

def _make_summary(state: Dict) -> str:
    sys_prompt = (
        "다음 대화는 사용자의 여행 성향을 파악하기 위한 Q&A입니다.\n"
        "사용자의 답변을 한 단락으로 누락 없이 정리하세요."
    )
    llm_input = [{"role": "system", "content": sys_prompt}] + state["messages"]
    return llm.invoke(llm_input).content.strip()