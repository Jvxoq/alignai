from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "alignai_docs"
    gemini_api_key: str = ""
    embedding_model: str = "text-embedding-004"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
