from typing import TypedDict, List
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph_supervisor import create_supervisor

import pandas as pd
from dotenv import load_dotenv
import getpass
import os

load_dotenv(override=True)
def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")
_set_env("OPENAI_API_KEY")

llm = ChatOpenAI(model='gpt-4o-mini')

class MyState(TypedDict):
    User_id: int
    Profile: str
    rec_people: List[int]
    summary: str

#################### csv 파일 경로 ####################
PATH = "/Users/nayoung/SiNear/prac.csv"
#####################################################

def profiler_node(state: MyState)-> MyState:
    '''
    해당 User_id의 messages와 feature를 이용하여 Profile을 생성하는 에이전트입니다. 
    '''
    
    id = state['User_id']
    df = pd.read_csv(PATH)
    try:
        feature = df[df['User_id'] == id].to_dict(orient="records")[0]
    except IndexError:
        feature = {}
    # print(feature)

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

    # response = llm.invoke(prompt).content
    # state['Profile'] = response
    # return state

    profile = llm.invoke(prompt).content
    return {"Profile": profile}
    

# 테스트 실행 
profiler = StateGraph(MyState)
profiler.add_node("profiler", profiler_node)
profiler.add_edge(START, "profiler")
profiler.add_edge("profiler", END)

app = profiler.compile()

example_input = {
    "User_id": 99808433,
    "Profile": "",
    "rec_people": [],
    "summary": "여행 갈 때는 꼭 계획을 미리 세우고 가는 스타일이에요. 관광 명소는 빠짐없이 다 둘러보고 싶고, 시간 낭비하는 건 싫어요."
}

# 실행 결과
result = app.invoke(example_input)
print("생성된 Profile:", result["Profile"])