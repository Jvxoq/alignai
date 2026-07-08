from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ROOT_ENV_FILE, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Vector DB
    QDRANT_URL: str
    QDRANT_API_KEY: str
    QDRANT_COLLECTION_NAME: str

    # LLM
    GROQ_API_KEY: str
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    INTENT_LLM_MODEL: str = "openai/gpt-oss-120b"
    GENERATOR_LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_RETRIES: int = 3

    # Embedding
    GEMINI_API_KEY: str
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSIONS: int = 3072

    # Observability
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT_NAME: str = "alignai"
    LANGCHAIN_TRACING_V2: bool = True

    # Retrieval
    SIMILARITY_THRESHOLD: float = 0.75
    RETRIEVAL_TOP_K: int = 3
    MAX_MESSAGE_LENGTH: int = 2000
    USER_MESSAGE_THRESHOLD: int = 50

    # App
    ENVIRONMENT: str = "development"
    DEV_MODE: bool = False

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
