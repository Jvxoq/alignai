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

    # Keep-alive: periodically pings the LangGraph agent's health endpoint so
    # a free-tier instance never sits idle long enough to spin down. Render's
    # free web services sleep after ~15 min without inbound traffic, so the
    # interval must stay comfortably under that.
    AGENT_KEEP_ALIVE_ENABLED: bool = True
    AGENT_KEEP_ALIVE_INTERVAL_SECONDS: int = 600
    AGENT_KEEP_ALIVE_TIMEOUT_SECONDS: int = 30

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
    MAX_SESSIONS_PER_USER: int = 3
    SIMILARITY_THRESHOLD: float = 0.75
    RETRIEVAL_TOP_K: int = 3
    DEV_MODE: bool = False

    @field_validator("LANGGRAPH_SERVER_URL")
    @classmethod
    def ensure_langgraph_url_scheme(cls, v: str) -> str:
        # The backend talks to the agent over Render's private network, which
        # uses plain http:// internal hostnames (e.g. "alignai-agent:10000").
        # Default a scheme-less value to http:// so internal traffic isn't
        # forced onto https and rejected. Public URLs should include their
        # own explicit scheme.
        if v and not v.startswith(("http://", "https://")):
            return f"http://{v}"
        return v

    @field_validator("POSTGRES_URL")
    @classmethod
    def normalize_postgres_url(cls, v: str) -> str:
        # Let a raw Neon connection string work as-is. Neon hands out
        # "postgresql://...?sslmode=require", but SQLAlchemy's async engine
        # needs the +asyncpg scheme, and asyncpg spells the SSL param "ssl="
        # (not psycopg's "sslmode="). Local dev URLs already use +asyncpg and
        # carry no sslmode, so both rewrites are no-ops there.
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "sslmode=" in v:
            v = v.replace("sslmode=", "ssl=", 1)
        return v

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
