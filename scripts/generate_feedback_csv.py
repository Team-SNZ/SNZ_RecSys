import pandas as pd
import random
import os

def create_feedback_csv(input_file_path: str, output_file_path: str, num_pairs_per_user: int = 3):
    """
    User_100.csv에서 사용자 ID와 프로필을 읽어,
    가상의 피드백 점수를 포함한 CSV 파일을 생성합니다.

    Args:
        input_file_path (str): 원본 CSV 파일 경로 ('User_100.csv').
        output_file_path (str): 생성할 피드백 CSV 파일 경로.
        num_pairs_per_user (int): 각 사용자당 생성할 긍정/부정 쌍의 수.
    """
    print("="*50)
    print("피드백 CSV 파일 생성 시작")
    print("="*50)

    # --- 1. 원본 CSV 파일 로드 ---
    try:
        df = pd.read_csv(input_file_path, encoding='utf-8-sig')
        print(f"'{input_file_path}' 파일 로드 성공.")
    except FileNotFoundError:
        print(f"오류: '{input_file_path}' 파일을 찾을 수 없습니다.")
        print("스크립트를 실행하기 전에 파일 경로를 확인해주세요.")
        return

    # --- 2. 유효한 사용자 ID 목록 추출 ---
    # Profile이 비어있지 않은 사용자만 대상으로 함
    valid_users_df = df.dropna(subset=['Profile'])
    valid_users_df = valid_users_df[valid_users_df['Profile'].str.strip() != '']
    all_user_ids = valid_users_df['ID'].unique().tolist()
    
    if not all_user_ids:
        print("오류: 처리할 유효한 사용자가 없습니다.")
        return
        
    print(f"총 {len(all_user_ids)}명의 유효한 사용자 프로필을 확인했습니다.")

    # --- 3. 가상 피드백 데이터 생성 ---
    feedback_records = []
    
    for user_a in all_user_ids:
        # 자기 자신을 제외한 나머지 사용자 ID 풀
        other_users = [uid for uid in all_user_ids if uid != user_a]
        
        # 샘플링할 사용자가 충분한지 확인
        if len(other_users) < num_pairs_per_user * 2:
            print(f"경고: user_id={user_a}의 파트너 후보가 부족하여 건너뜁니다.")
            continue

        # 긍정적/부정적 관계를 만들 사용자 샘플링
        sampled_partners = random.sample(other_users, k=num_pairs_per_user * 2)
        
        # 긍정적 쌍 생성
        positive_partners = sampled_partners[:num_pairs_per_user]
        for user_b in positive_partners:
            score = random.choice([4, 5])
            feedback_records.append({
                'user_id_A': user_a,
                'user_id_B': user_b,
                'score': score
            })
            
        # 부정적 쌍 생성
        negative_partners = sampled_partners[num_pairs_per_user:]
        for user_b in negative_partners:
            score = random.choice([1, 2])
            feedback_records.append({
                'user_id_A': user_a,
                'user_id_B': user_b,
                'score': score
            })

    # --- 4. 데이터프레임으로 변환 및 CSV 파일로 저장 ---
    if not feedback_records:
        print("오류: 생성된 피드백 데이터가 없습니다.")
        return

    feedback_df = pd.DataFrame(feedback_records)
    
    # 생성된 파일의 경로를 확인하고, 폴더가 없으면 생성
    output_dir = os.path.dirname(output_file_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    feedback_df.to_csv(output_file_path, index=False, encoding='utf-8-sig')
    
    print("\n" + "-"*50)
    print(f"피드백 파일 생성 완료: '{output_file_path}'")
    print(f"  - 총 생성된 피드백 쌍: {len(feedback_df)}개")
    print(f"  - 긍정적 쌍(4-5점): {len(feedback_df[feedback_df['score'] >= 4])}개")
    print(f"  - 부정적 쌍(1-2점): {len(feedback_df[feedback_df['score'] <= 2])}개")
    print("-" * 50)


if __name__ == '__main__':
    # 입력 파일 경로: User_100.csv
    INPUT_CSV_PATH = 'langchain/SNZ_RecSys/User_100.csv'
    
    # 출력 파일 경로: feedback_data.csv
    OUTPUT_CSV_PATH = 'langchain/SNZ_RecSys/synthetic_feedback_data.csv'
    
    create_feedback_csv(input_file_path=INPUT_CSV_PATH, output_file_path=OUTPUT_CSV_PATH)
