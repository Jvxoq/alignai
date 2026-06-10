from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "alignai_docs"
    qdrant_api_key: str = ""
    gemini_api_key: str = ""
    embedding_model: str = "gemini-embedding-001"
    log_level: str = "INFO"

    retrieval_top_k: int = 3
    similarity_threshold: float = 0.75
    embedding_batch_size: int = 20
    embedding_batch_delay: float = 2.0
    embedding_max_retries: int = 3

    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3-32b"
    llm_max_retries: int = 3
    recital_end_page: int = 43

    dev_mode: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
