from app.core.config import Settings, get_settings


REQUIRED_ENV = {
    "QDRANT_URL": "http://localhost:6333",
    "QDRANT_API_KEY": "key",
    "QDRANT_COLLECTION_NAME": "collection",
    "GROQ_API_KEY": "groq-key",
    "GEMINI_API_KEY": "gemini-key",
}


def test_loads_from_env(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", REQUIRED_ENV["QDRANT_URL"])
    monkeypatch.setenv("QDRANT_API_KEY", REQUIRED_ENV["QDRANT_API_KEY"])
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", REQUIRED_ENV["QDRANT_COLLECTION_NAME"])
    monkeypatch.setenv("GROQ_API_KEY", REQUIRED_ENV["GROQ_API_KEY"])
    monkeypatch.setenv("GEMINI_API_KEY", REQUIRED_ENV["GEMINI_API_KEY"])

    settings = Settings(_env_file=None)

    assert settings.QDRANT_URL == REQUIRED_ENV["QDRANT_URL"]
    assert settings.QDRANT_API_KEY == REQUIRED_ENV["QDRANT_API_KEY"]
    assert settings.QDRANT_COLLECTION_NAME == REQUIRED_ENV["QDRANT_COLLECTION_NAME"]
    assert settings.GROQ_API_KEY == REQUIRED_ENV["GROQ_API_KEY"]
    assert settings.GEMINI_API_KEY == REQUIRED_ENV["GEMINI_API_KEY"]


def test_defaults(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    settings = Settings(_env_file=None)

    assert settings.LLM_MODEL == "llama-3.3-70b-versatile"
    assert settings.INTENT_LLM_MODEL == "llama-3.3-70b-versatile"
    assert settings.GENERATOR_LLM_MODEL == "llama-3.3-70b-versatile"
    assert settings.LLM_TEMPERATURE == 0.1
    assert settings.LLM_MAX_RETRIES == 3
    assert settings.EMBEDDING_MODEL == "gemini-embedding-001"
    assert settings.EMBEDDING_DIMENSIONS == 3072
    assert settings.SIMILARITY_THRESHOLD == 0.75
    assert settings.RETRIEVAL_TOP_K == 3
    assert settings.MAX_MESSAGE_LENGTH == 2000
    assert settings.USER_MESSAGE_THRESHOLD == 50
    assert settings.ENVIRONMENT == "development"
    assert settings.DEV_MODE is False
    assert settings.LANGCHAIN_TRACING_V2 is True


def test_is_production_property(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)

    dev_settings = Settings(_env_file=None)
    assert dev_settings.is_production is False

    monkeypatch.setenv("ENVIRONMENT", "production")
    prod_settings = Settings(_env_file=None)
    assert prod_settings.is_production is True


def test_get_settings_is_cached():
    assert get_settings() is get_settings()


def test_intent_and_generator_models_are_independently_overridable(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("INTENT_LLM_MODEL", "llama-3.1-8b-instant")

    settings = Settings(_env_file=None)

    assert settings.INTENT_LLM_MODEL == "llama-3.1-8b-instant"
    assert settings.GENERATOR_LLM_MODEL == "llama-3.3-70b-versatile"
    assert settings.LLM_MODEL == "llama-3.3-70b-versatile"
