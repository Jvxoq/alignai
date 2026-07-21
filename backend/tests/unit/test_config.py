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


def test_raw_neon_url_becomes_valid_asyncpg_url():
    # The exact string Neon's dashboard hands out, pasted raw: +asyncpg dialect,
    # sslmode= -> ssl= (asyncpg's spelling), and channel_binding dropped (asyncpg
    # has no such connect kwarg — leaving it in raises on the first connection).
    settings = _make_settings(
        POSTGRES_URL=(
            "postgresql://u:p@ep-x.neon.tech/db?sslmode=require&channel_binding=require"
        )
    )
    assert (
        settings.POSTGRES_URL
        == "postgresql+asyncpg://u:p@ep-x.neon.tech/db?ssl=require"
    )


def test_bare_postgres_scheme_also_gets_asyncpg_dialect():
    # Some tools/CLIs emit "postgres://" rather than "postgresql://"; without a
    # dialect SQLAlchemy can't load a driver, so it must be rewritten too.
    settings = _make_settings(
        POSTGRES_URL="postgres://u:p@ep-x.neon.tech/db?sslmode=require"
    )
    assert (
        settings.POSTGRES_URL
        == "postgresql+asyncpg://u:p@ep-x.neon.tech/db?ssl=require"
    )


def test_local_asyncpg_url_passed_through_unchanged():
    url = "postgresql+asyncpg://postgres:password@postgres:5432/alignai"
    settings = _make_settings(POSTGRES_URL=url)
    assert settings.POSTGRES_URL == url
