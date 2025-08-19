# SNZ RecSys - 여행 추천 시스템

LangGraph 기반의 Multi-Agent 여행 추천 시스템입니다.

## 📋 주요 기능

- **프로필 생성**: 사용자의 여행 성향과 대화 요약을 기반으로 프로필 생성
- **유사 사용자 검색**: FAISS 벡터스토어를 활용한 유사 사용자 검색
- **동행자 추천**: 프로필 호환성 분석을 통한 동행자 추천
- **여행지 추천**: 사용자와 동행자 성향을 고려한 여행지 추천

## 🏗️ 아키텍처

### Multi-Agent 구조
- **Supervisor Agent**: 전체 워크플로우 관리
- **Profiler Agent**: 사용자 프로필 생성
- **Retriever Agent**: 유사 사용자 검색
- **Recommender Agent**: 동행자 및 여행지 추천

### 기술 스택
- **LangGraph**: Agent 워크플로우 관리
- **LangChain**: LLM 통합 및 프롬프트 관리
- **FastAPI**: REST API 서버
- **MongoDB**: 사용자 데이터 저장
- **FAISS**: 벡터 유사도 검색
- **OpenAI**: GPT 모델 활용

## 🚀 설치 및 실행

### 방법 1: 통합 시스템 Docker 배포 (권장)

WiNear 백엔드와 RecSys Agent가 통합된 시스템을 쉽게 배포할 수 있습니다.

#### 1. 프로젝트 구조 확인
```
PycharmProjects/
├── WiNear-backend/     # WiNear 백엔드 API
└── SNZ_RecSys/         # RecSys Agent (현재 위치)
```

#### 2. 초기 설정
```bash
cd SNZ_RecSys

# 초기 설정 (SSL 인증서 생성, 환경변수 템플릿 생성)
./winear-deploy.sh setup

# .env 파일에서 OpenAI API 키 설정
nano .env
```

#### 3. 시스템 시작
```bash
# 개발 환경 (코드 변경 시 자동 리로드)
./winear-deploy.sh dev

# 프로덕션 환경
./winear-deploy.sh prod

# 상태 확인
./winear-deploy.sh status
```

#### 4. 서비스 접속
**통합 API Gateway (Nginx):**
- Main: https://localhost
- WiNear API: https://localhost/api/
- RecSys Agent: https://localhost/recsys/
- API 문서: https://localhost/docs (WiNear), https://localhost/recsys/docs (RecSys)

**개별 서비스 직접 접근:**
- WiNear API: http://localhost:8001
- RecSys Agent: http://localhost:8002
- MongoDB: localhost:27017

#### 5. 시스템 관리
```bash
# 로그 확인
./winear-deploy.sh logs                    # 모든 서비스
./winear-deploy.sh logs winear-api         # 특정 서비스

# 서비스 재시작
./winear-deploy.sh restart

# 시스템 중지
./winear-deploy.sh stop

# API 테스트
./winear-deploy.sh test

# 정리 (볼륨 및 이미지 삭제)
./winear-deploy.sh clean
```

### 방법 2: 개별 Docker 실행

#### RecSys Agent만 실행
```bash
# 개발 환경
docker-compose up -d recsys-agent mongodb

# 프로덕션 환경
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d recsys-agent mongodb
```

### 방법 3: 로컬 개발 환경

#### 1. 프로젝트 클론
```bash
git clone <repository-url>
cd SNZ_RecSys
```

#### 2. uv 설치 (Python 패키지 매니저)
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### 3. 의존성 설치
```bash
uv sync
```

#### 4. 환경변수 설정
`.env` 파일을 생성하고 다음 변수들을 설정하세요:

```env
# MongoDB 설정
WINEAR_MONGODB_URI=mongodb://localhost:27017
WINEAR_MONGODB_DB=travel_recsys
WINEAR_MONGODB_SERVER_API=1

# OpenAI 설정
WINEAR_OPENAI_API_KEY=sk-your-openai-api-key-here
WINEAR_OPENAI_MODEL=gpt-4o
WINEAR_OPENAI_TEMPERATURE=0.3

# 벡터스토어 설정
WINEAR_FAISS_DIR=./faiss_user_profiles
WINEAR_EMBEDDING_MODEL=text-embedding-3-small

# 추천 시스템 설정
WINEAR_RETRIEVAL_TOTAL_K=120
WINEAR_RETRIEVAL_TOP_K=100
WINEAR_PEOPLE_REC_TOP_K=10
WINEAR_TRAVEL_REC_TOP_K=3

# CORS 설정
WINEAR_ALLOWED_ORIGINS=["*"]
```

#### 5. MongoDB 설정
MongoDB가 실행 중이어야 하며, 다음 컬렉션들이 필요합니다:
- `user_features`: 사용자 여행 성향 데이터
- `user_summary`: 사용자 대화 요약
- `user_profile`: 생성된 사용자 프로필
- `user_recs`: 추천 결과
- `travel_info`: 여행 상품 정보

#### 6. 서버 실행
```bash
# 개발 서버
uv run uvicorn app.main:app --reload

# 프로덕션 서버
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📚 API 사용법

### 여행 추천 요청
```http
POST /agent/recommend
Content-Type: application/json

{
    "user_id": "user123",
    "profile": ""  # 선택사항: 기존 프로필이 있으면 생략 가능
}
```

### 응답 예시
```json
{
    "user_id": "user123",
    "rec_people": ["user456", "user789", "user101"],
    "rec_travel": ["PROD001", "PROD002", "PROD003"],
    "status": "success"
}
```

### 헬스체크
```http
GET /agent/health
```

## 🔧 개발 가이드

### 프로젝트 구조
```
app/
├── core/
│   └── config.py              # 설정 관리
├── dependencies/
│   ├── db.py                  # DB 의존성
│   ├── llm.py                 # LLM 의존성
│   └── collections.py         # MongoDB 컬렉션 의존성
├── graph/
│   ├── state.py               # LangGraph 상태 정의
│   ├── nodes.py               # Agent 노드들
│   └── tools.py               # Agent 도구들
├── prompts/
│   ├── profiler_prompts.py    # 프로필 생성 프롬프트
│   └── recommender_prompts.py # 추천 프롬프트
├── services/
│   └── vectorstore.py         # 벡터스토어 관리
├── utils/
│   └── profile_parser.py      # 프로필 파싱 유틸
├── routers/
│   └── agent.py               # API 라우터
├── agent.py                   # 메인 Agent 클래스
└── main.py                    # FastAPI 앱
```

### 새로운 프롬프트 추가
1. `app/prompts/` 디렉토리에 새 파일 생성
2. LangChain의 `PromptTemplate` 사용
3. 프롬프트 포맷팅 함수 제공

### 새로운 Agent 노드 추가
1. `app/graph/nodes.py`에 노드 함수 추가
2. `app/agent.py`의 그래프에 노드 등록
3. 상태 전이 로직 구현

## 🐳 Docker 관리

### 유용한 Docker 명령어

```bash
# 컨테이너 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f api
docker-compose logs mongodb

# 컨테이너 재시작
docker-compose restart api

# 데이터베이스 백업
docker exec snz_mongodb mongodump --db travel_recsys --out /data/backup

# 볼륨 확인
docker volume ls

# 컨테이너 정리
docker-compose down
docker system prune -f
```

### 빌드 및 배포

```bash
# 이미지 빌드
docker build -t snz-recsys:latest .

# 프로덕션 빌드
docker build --target production -t snz-recsys:prod .

# 이미지 태그 및 푸시
docker tag snz-recsys:prod your-registry/snz-recsys:v1.0.0
docker push your-registry/snz-recsys:v1.0.0
```

## 🔍 모니터링

### 로그 확인
```bash
# Docker 환경
docker-compose logs -f api

# 로컬 환경
uv run uvicorn app.main:app --log-level debug

# 파일 로그 (설정 필요)
tail -f logs/app.log
```

### 헬스체크
```bash
# API 상태 확인
curl http://localhost:8000/health

# 에이전트 상태 확인
curl http://localhost:8000/agent/health
```

### 성능 메트릭
- 프로필 생성 시간
- 벡터 검색 시간
- 전체 추천 시간
- LLM API 호출 횟수

## 🤝 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다.
