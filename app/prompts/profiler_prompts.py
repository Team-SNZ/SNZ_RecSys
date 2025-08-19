from langchain_core.prompts import PromptTemplate
from typing import Dict, Any


def create_profile_prompt_template() -> PromptTemplate:
    """
    사용자 프로필 생성을 위한 프롬프트 템플릿
    """
    template = """당신은 여행 동반자 매칭 서비스를 위한 프로파일 생성 에이전트입니다.
    다음은 한 사용자의 여행 성향 데이터와 대화 요약입니다.
    
    [핵심 여행 정보]
    {important_features}

    [전체 여행 성향 피쳐]
    {all_features}

    [대화 요약]
    {summary}

    [지시사항]
    1. "중요 요소"에는 핵심 여행 정보의 모든 항목을 반드시 포함하세요.
    2. "피하는 요소"에는 핵심 여행 정보와 대화 요약에서 드러난 기피 성향을 모두 포함하세요.
    3. "요약"에는 핵심 여행 정보와 대화 요약을 모두 고려해, 최대한 구체적으로 작성하세요.
    4. 핵심 여행 정보와 대화 요약 내용이 상충하면 핵심 여행 정보를 우선합니다.
    5. 출력 형식은 아래와 같이 정확히 지켜주세요. 다른 설명은 절대 포함하지 마세요.

    <출력 형식>
    - 중요 요소: <콤마로 구분된 키워드>
    - 피하는 요소: <콤마로 구분된 키워드>
    - 요약: <문장>
    """
    
    return PromptTemplate(
        input_variables=["important_features", "all_features", "summary"],
        template=template
    )


def format_features_for_prompt(important_features: Dict[str, Any], all_features: Dict[str, Any]) -> tuple[str, str]:
    """
    피쳐 딕셔너리들을 프롬프트용 문자열로 포맷팅
    """
    important_str = "\n".join([f"- {k}: {v}" for k, v in important_features.items()])
    all_str = "\n".join([f"- {k}: {v}" for k, v in all_features.items()])
    
    return important_str, all_str
