import os

# Live tests (tests/integration, RUN_LIVE_TESTS=1) need the real .env values,
# not these CI fallbacks -- env vars outrank the .env file in pydantic-settings.
if os.getenv("RUN_LIVE_TESTS") != "1":
    os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
    os.environ.setdefault("QDRANT_API_KEY", "test-qdrant-key")
    os.environ.setdefault("QDRANT_COLLECTION_NAME", "test_collection")
    os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
    os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
