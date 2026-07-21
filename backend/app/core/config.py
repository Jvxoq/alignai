from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
        # Let a raw Neon connection string work as-is. Neon (and many tools/CLIs)
        # hand out something like
        #   postgres[ql]://u:p@host/db?sslmode=require&channel_binding=require
        # but SQLAlchemy's async engine needs the "+asyncpg" dialect, and asyncpg
        # rejects psycopg-style query params: it spells the SSL mode "ssl="
        # (not "sslmode="), and it has no "channel_binding" connect kwarg at all
        # (channel binding is negotiated automatically). Forwarding either param
        # unchanged makes the first connection raise. Local dev URLs already use
        # "+asyncpg" and carry no query params, so this is a no-op there.
        if not v:
            return v

        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                v = "postgresql+asyncpg://" + v[len(prefix):]
                break

        parts = urlsplit(v)
        if parts.query:
            normalized: list[tuple[str, str]] = []
            for key, value in parse_qsl(parts.query, keep_blank_values=True):
                if key == "sslmode":
                    normalized.append(("ssl", value))
                elif key == "channel_binding":
                    continue  # not an asyncpg connect kwarg — drop it
                else:
                    normalized.append((key, value))
            v = urlunsplit(parts._replace(query=urlencode(normalized)))
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
