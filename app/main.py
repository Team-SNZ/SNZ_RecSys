from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from urllib.parse import urlparse, urlunparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi

from .core.config import get_settings
from .routers.agent import router as agent_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Settings 내 환경 변수 설정
    settings = get_settings()

    # MongoDB 연결 생성
    client_kwargs: dict[str, object] = {}
    if settings.mongodb_server_api:
        client_kwargs["server_api"] = ServerApi(settings.mongodb_server_api)
    client = AsyncIOMotorClient(settings.mongodb_uri, **client_kwargs)

    # 연결 핑 및 URI 로깅
    logger = logging.getLogger("uvicorn.error")

    def _mask_mongo_uri(uri: str) -> str:
        parsed = urlparse(uri)
        netloc = parsed.netloc
        if "@" in netloc:
            host_part = netloc.split("@", 1)[1]
            netloc = f"***:***@{host_part}"
        masked = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
        return masked

    try:
        await client.admin.command("ping")
        logger.info(f"Connected to MongoDB: {_mask_mongo_uri(settings.mongodb_uri)} / db={settings.mongodb_db}")
    except Exception as exc:
        logger.error(f"[------------[MongoDB connection failed]----------------\n{exc}")
        raise
    app.state.mongo_client = client
    app.state.mongo_db = client[settings.mongodb_db]

    yield
    client.close()


settings = get_settings()
app = FastAPI(title="WiNear API - RecSys Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"], summary="헬스 체크")  # liveness probe
def health() -> dict[str, str]:
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


app.include_router(agent_router)