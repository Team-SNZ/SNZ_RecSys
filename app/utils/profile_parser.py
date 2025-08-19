import re
from typing import Dict


def parse_profile_output(text: str) -> Dict[str, str]:
    """
    LLM 응답에서 중요 요소, 피하는 요소, 요약을 파싱해서 dict로 반환
    
    Args:
        text: LLM이 생성한 프로필 텍스트
        
    Returns:
        파싱된 프로필 딕셔너리
    """
    important = re.search(r"(?<=- 중요 요소:).*?(?=\n- 피하는 요소:)", text, re.DOTALL)
    avoid = re.search(r"(?<=- 피하는 요소:).*?(?=\n- 요약:)", text, re.DOTALL)
    summary = re.search(r"(?<=- 요약:).*", text, re.DOTALL)

    return {
        "important": important.group(0).strip() if important else "",  # 중요 요소
        "avoid": avoid.group(0).strip() if avoid else "",              # 피하는 요소
        "summary": summary.group(0).strip() if summary else ""         # 요약
    }
