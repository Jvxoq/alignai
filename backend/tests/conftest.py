import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-for-anything-real-123456")
os.environ.setdefault("POSTGRES_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("LANGGRAPH_SERVER_URL", "http://localhost:8123")
