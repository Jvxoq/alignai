from app.core.config import Settings


def _make_settings(**overrides) -> Settings:
    base = dict(
        SECRET_KEY="test-secret-key-not-used-for-anything-real-123456",
        POSTGRES_URL="postgresql+asyncpg://test:test@localhost:5432/test",
        LANGGRAPH_SERVER_URL="http://localhost:8123",
    )
    base.update(overrides)
    return Settings(**base)


def test_scheme_less_agent_url_defaults_to_http():
    # Render's private network uses plain http:// internal hostnames. A
    # scheme-less value must not be forced onto https, or backend->agent
    # traffic breaks in prod.
    settings = _make_settings(LANGGRAPH_SERVER_URL="alignai-agent:10000")
    assert settings.LANGGRAPH_SERVER_URL == "http://alignai-agent:10000"


def test_explicit_http_scheme_is_preserved():
    settings = _make_settings(LANGGRAPH_SERVER_URL="http://agent:8123")
    assert settings.LANGGRAPH_SERVER_URL == "http://agent:8123"


def test_explicit_https_scheme_is_preserved():
    settings = _make_settings(LANGGRAPH_SERVER_URL="https://agent.example.com")
    assert settings.LANGGRAPH_SERVER_URL == "https://agent.example.com"


def test_neon_url_gets_asyncpg_scheme_and_ssl_param():
    # A raw Neon connection string must become a valid asyncpg URL: +asyncpg
    # scheme and ssl= (asyncpg's spelling) instead of sslmode=.
    settings = _make_settings(
        POSTGRES_URL="postgresql://u:p@ep-x.neon.tech/db?sslmode=require"
    )
    assert (
        settings.POSTGRES_URL
        == "postgresql+asyncpg://u:p@ep-x.neon.tech/db?ssl=require"
    )


def test_local_asyncpg_url_passed_through_unchanged():
    url = "postgresql+asyncpg://postgres:password@postgres:5432/alignai"
    settings = _make_settings(POSTGRES_URL=url)
    assert settings.POSTGRES_URL == url
