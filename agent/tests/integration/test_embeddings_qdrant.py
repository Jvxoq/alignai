import os

import pytest

from app.infrastructure.embeddings import embed_text
from app.infrastructure.qdrant_client import get_qdrant_client, search_chunks
from app.core.config import get_settings

# Hits live Gemini + Qdrant. Opt in with RUN_LIVE_TESTS=1; mocked
# coverage lives in tests/unit/test_embeddings.py.
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="live infra test; set RUN_LIVE_TESTS=1 to run",
)


@pytest.fixture(autouse=True)
def _fresh_qdrant_client():
    # get_qdrant_client() is lru_cache'd, but pytest-asyncio gives each test
    # its own event loop -- a client cached from a prior test holds a dead
    # loop. Drop the cache so each test builds its client on its own loop.
    get_qdrant_client.cache_clear()


@pytest.mark.asyncio
async def test_embed_text_returns_real_vector():
    settings = get_settings()

    vector = await embed_text("What are the requirements for high-risk AI systems?")

    assert len(vector) == settings.EMBEDDING_DIMENSIONS
    assert any(v != 0 for v in vector)


@pytest.mark.asyncio
async def test_qdrant_collection_reachable():
    settings = get_settings()
    client = get_qdrant_client()

    exists = await client.collection_exists(settings.QDRANT_COLLECTION_NAME)

    assert exists is True


@pytest.mark.asyncio
async def test_embed_then_search_round_trip():
    vector = await embed_text("obligations for providers of high-risk AI systems")

    results = await search_chunks(vector, top_k=3)

    assert isinstance(results, list)
    assert len(results) <= 3
    for hit in results:
        assert "id" in hit
        assert "score" in hit
        assert "payload" in hit
        print(f"score={hit['score']:.3f} article={hit['payload'].get('article_number')}")
