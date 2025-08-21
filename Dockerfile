# ---------- Base ----------
FROM python:3.10-slim AS base

# uv 바이너리만 끌어오기
COPY --from=ghcr.io/astral-sh/uv:0.8.11 /uv /uvx /bin/

WORKDIR /app
# 의존성만 먼저 복사(캐시 최적화)
COPY pyproject.toml uv.lock* ./

# (옵션) 휠만 설치 강제해서 소스 빌드 방지
ENV UV_PIP_FLAGS="--only-binary=:all:"

RUN uv sync --frozen

# ---------- Development ----------
FROM base AS development
EXPOSE 8000
ENV PYTHONPATH=/app UVICORN_HOST=0.0.0.0 UVICORN_PORT=8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host","0.0.0.0","--port","8000","--reload"]

# ---------- Production ----------
FROM base AS production

# 런타임 유틸
RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

# 앱 코드 복사
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY *.py ./
COPY scripts/requirements.txt .

# Requirements.txt 설치
RUN pip install --no-cache-dir -r requirements.txt

# 데이터/로그 디렉토리
RUN mkdir -p faiss_user_profiles logs

# 비루트 사용자
RUN groupadd -r appuser && useradd -m -r -g appuser appuser
# 캐시 경로 지정 + 권한 보장
ENV XDG_CACHE_HOME=/home/appuser/.cache
RUN mkdir -p ${XDG_CACHE_HOME} && chown -R appuser:appuser /home/appuser

# FAISS 디렉토리 권한 설정
RUN chown -R appuser:appuser /app/faiss_user_profiles /app/logs

USER appuser

EXPOSE 8000
ENV PYTHONPATH=/app UVICORN_HOST=0.0.0.0 UVICORN_PORT=8000 PYTHONOPTIMIZE=1

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host","0.0.0.0","--port","8000","--workers","4"]