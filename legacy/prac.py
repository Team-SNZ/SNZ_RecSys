from pymongo import MongoClient
import pandas as pd

"""
새로운 유저가 들어왔을 떄 그 유저 ID 만들어서 설문조사 결과랑 자동으로 저장이 되는지 코드로 확인하기
"""

client = MongoClient("mongodb+srv://sjy21ys:cjdthdtla12!@cluster0.ozrm81h.mongodb.net/")

db = client["travel_recsys"]
travel_info = db["travel_info"]
print(travel_info.find_one())
# doc = col_features.find().skip(1001).limit(1)
# print(list(doc))

def save_new_user_features(user_id: str, features: dict):
    """
    새로운 사용자 ID의 Features를 MongoDB에 저장
    """
    required_keys = [
        "예민함정도", "의견수용", "말수", "시간약속", "리더십", "체력", "청결민감도",
        "여행일정강도", "국내or해외", "산or바다", "계획or즉흥", "랜드마크", "코골이",
        "웨이팅", "여행희망지역", "싫어하는기후", "여행목적", "숙소유형", "기상시간", "여행예산"
    ]

    # 누락된 키 → 빈 문자열로 채움
    for key in required_keys:
        if key not in features:
            features[key] = ""
    
    col_features.update_one(
        {"ID": user_id},
        {"$set": {"ID": user_id, "Features": features}},
        upsert=True
    )

    print(f"사용자 ID: {user_id}의 설문 조사 결과 MongoDB에 저장 완료")

# print(col_features.find_one({"ID": "nayoung"}))
# if __name__ == "__main__":
#     features = {
#         "예민함정도": "보통",
#         "의견수용": "매우 수용적",
#         "말수": "많다",
#         "시간약속": "자주 늦음",
#         "리더십": "따르는 편",
#         "체력": 4
#     }
#     save_new_user_features("nayoung", features)


# 여행일정강도, 국내or해외, 산or바다, 랜드마크, 여행희망지역, 싫어하는기후, 여행목적, 숙소유형, 여행예산

# """
# User_1000의 ID를 int -> str로 변경
# """

# path = '/Users/nayoung/SiNear/prac.csv'
# df = pd.read_csv(path)

# # print(df["ID"][0])
# # print(type(df["ID"][0]))

# for i in range(len(df)):
#     # df["ID"][i] = str(df["ID"][i]) + "asd"
#     # print(df["ID"][i])
#     print(type(df["ID"][i]))

# # df.to_csv('/Users/nayoung/SiNear/prac.csv', index=False)