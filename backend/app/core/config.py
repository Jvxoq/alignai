from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

import json


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # LangGraph
    LANGGRAPH_SERVER_URL: str
    LANGGRAPH_CONNECTION_TIMEOUT: int = 10
    LANGGRAPH_READ_TIMEOUT: int = 60

    # Database
    POSTGRES_URL: str

    # LLM + Embedding
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Observability
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT_NAME: str = "alignai"
    LANGCHAIN_TRACING_V2: bool = True

    # Auth
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost"]
    MAX_MESSAGE_LENGTH: int = 2000
    USER_MESSAGE_THRESHOLD: int = 50
    SIMILARITY_THRESHOLD: float = 0.75
    RETRIEVAL_TOP_K: int = 3
    DEV_MODE: bool = False

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("SECRET_KEY must be set")
        return v

    @field_validator("CORS_ORIGINS", mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @model_validator(mode='after')
    def validate_production_settings(self):
        if self.ENVIRONMENT == "production":
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be at least 32 chars in production")
            if "*" in self.CORS_ORIGINS:
                raise ValueError(
                    "CORS allow_origins=['*'] cannot be used in production. "
                    "Set CORS_ORIGINS to your frontend URL."
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
