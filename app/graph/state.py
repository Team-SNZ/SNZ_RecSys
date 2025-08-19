from typing import TypedDict, List


class MyState(TypedDict, total=False):
    user_id: str
    profile: str                               # user 요약 정보
    rec_people: List[str]                      # 매칭 후보 id
    rec_travel: List[str]                      # 추천 여행지 link
    top_100_ids: List[str]                     # retrieved user ids