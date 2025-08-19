from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # MongoDB 설정
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "travel_recsys"  # 실제 사용하는 DB명으로 변경
    allowed_origins: list[str] = ["*"]
    
    # MongoDB Server API (Atlas 권장). 예: "1" (기본 활성화)
    mongodb_server_api: str | None = "1"

    # OpenAI / LLM 설정
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.3
    
    # 벡터스토어 설정
    faiss_dir: str = "./faiss_user_profiles"
    embedding_model: str = "text-embedding-3-small"
    
    # 추천 시스템 설정
    retrieval_total_k: int = 120
    retrieval_top_k: int = 100
    people_rec_top_k: int = 10
    travel_rec_top_k: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WINEAR_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

