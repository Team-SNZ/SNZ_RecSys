# MongoDB 모킹 데이터 생성 스크립트

## 개요

`generate_mock_data.py`는 기존 CSV 데이터를 기반으로 MongoDB에 모킹 데이터를 자동으로 생성하는 스크립트입니다.

## 주요 기능

- **사용자 데이터 확장**: 기존 `User_1000_str.csv` 데이터에 이름, 성별, 나이(50세 이상) 정보 추가
- **여행 데이터 삽입**: `final_travel.csv` 데이터를 MongoDB에 구조화하여 저장
- **MongoDB 컬렉션 구성**:
  - `user_features`: 사용자 특성 및 프로필 정보
  - `user_profile`: 사용자 여행 성향 프로필
  - `user_summary`: 사용자 요약 정보
  - `user_recs`: 사용자 추천 데이터
  - `travel_info`: 여행 상품 정보
  - `travel_url`: 여행 상품 URL

## 설치 및 설정

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. MongoDB 설정

#### 로컬 MongoDB 사용
```bash
# MongoDB가 로컬에서 실행 중이어야 함 (기본 포트 27017)
```

#### MongoDB Atlas 사용
스크립트의 `main()` 함수에서 `mongodb_uri` 변수를 수정:
```python
mongodb_uri = "mongodb+srv://username:password@cluster.mongodb.net/"
```

또는 환경변수 설정:
```bash
export MONGODB_URI="mongodb+srv://username:password@cluster.mongodb.net/"
```

## 사용법

### 기본 실행
```bash
python generate_mock_data.py
```

### 실행 과정
1. 기존 사용자 데이터 삭제 (선택적)
2. CSV 파일 로드
3. 사용자별 랜덤 프로필 생성 (이름, 성별, 나이)
4. MongoDB에 데이터 삽입
5. 데이터 검증

## 생성되는 데이터 구조

### user_features 컬렉션
```json
{
  "ID": "1asd",
  "Features": {
    "예민함정도": "보통",
    "의견수용": "매우 수용적",
    // ... 기존 특성들
    "name": "김철수",
    "gender": "남성", 
    "age": 65
  }
}
```

### travel_info 컬렉션
```json
{
  "product_code": "AAP202250902TWA",
  "title": "방콕/파타야 5일 #첫여행추천",
  "description": "방콕&파타야를 처음 방문하시거나...",
  "hashtags": ["#관광+자유", "#관광"],
  "features": ["3박 5일", "LCC", "쇼핑없음"],
  "price": "749,000"
}
```

## 로그 확인

스크립트 실행 시 상세한 로그가 출력됩니다:
- MongoDB 연결 상태
- 데이터 삽입 진행률
- 최종 컬렉션별 문서 수
- 샘플 데이터 확인

## 주의사항

- 스크립트 실행 시 기존 사용자 데이터가 모두 삭제됩니다
- 여행 데이터도 기존 데이터가 삭제되고 새로 삽입됩니다
- 1000명의 사용자 데이터 처리에 수 분이 소요될 수 있습니다

## 트러블슈팅

### MongoDB 연결 오류
- MongoDB 서버가 실행 중인지 확인
- 연결 URI가 올바른지 확인
- 네트워크 방화벽 설정 확인

### CSV 파일 경로 오류
- `data/` 디렉토리에 CSV 파일들이 존재하는지 확인
- 파일 권한 확인

### 메모리 부족
- 큰 데이터셋의 경우 배치 단위로 처리하도록 스크립트 수정 가능
