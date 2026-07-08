from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.infrastructure.qdrant_client import ensure_collection, get_qdrant_client, upsert_chunks


def _settings(**overrides):
    base = dict(
        QDRANT_URL="http://localhost:6333",
        QDRANT_API_KEY="test-key",
        QDRANT_COLLECTION_NAME="eu_ai_act",
        EMBEDDING_DIMENSIONS=3072,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestGetQdrantClient:
    def test_builds_client_from_settings(self):
        get_qdrant_client.cache_clear()
        with patch("app.infrastructure.qdrant_client.get_settings", return_value=_settings()):
            client = get_qdrant_client()
        assert client is not None
        get_qdrant_client.cache_clear()

    def test_is_cached_across_calls(self):
        get_qdrant_client.cache_clear()
        with patch("app.infrastructure.qdrant_client.get_settings", return_value=_settings()):
            first = get_qdrant_client()
            second = get_qdrant_client()
        assert first is second
        get_qdrant_client.cache_clear()


class TestEnsureCollection:
    async def test_noop_when_collection_already_exists(self):
        mock_client = AsyncMock()
        mock_client.collection_exists.return_value = True

        with (
            patch("app.infrastructure.qdrant_client.get_settings", return_value=_settings()),
            patch("app.infrastructure.qdrant_client.get_qdrant_client", return_value=mock_client),
        ):
            await ensure_collection()

        mock_client.collection_exists.assert_awaited_once_with("eu_ai_act")
        mock_client.create_collection.assert_not_called()
        mock_client.create_payload_index.assert_not_called()

    async def test_creates_collection_and_payload_indexes_when_missing(self):
        mock_client = AsyncMock()
        mock_client.collection_exists.return_value = False

        with (
            patch("app.infrastructure.qdrant_client.get_settings", return_value=_settings()),
            patch("app.infrastructure.qdrant_client.get_qdrant_client", return_value=mock_client),
        ):
            await ensure_collection()

        mock_client.create_collection.assert_awaited_once()
        _, kwargs = mock_client.create_collection.call_args
        assert kwargs["collection_name"] == "eu_ai_act"
        assert kwargs["vectors_config"].size == 3072

        assert mock_client.create_payload_index.await_count == 5
        indexed_fields = {
            call.kwargs["field_name"] for call in mock_client.create_payload_index.await_args_list
        }
        assert indexed_fields == {
            "article_number",
            "chapter_number",
            "section_number",
            "is_recital",
            "recital_number",
        }


class TestUpsertChunks:
    async def test_empty_list_is_a_noop(self):
        mock_client = AsyncMock()

        with (
            patch("app.infrastructure.qdrant_client.get_settings", return_value=_settings()),
            patch("app.infrastructure.qdrant_client.get_qdrant_client", return_value=mock_client),
        ):
            await upsert_chunks([])

        mock_client.upsert.assert_not_called()

    async def test_builds_points_and_upserts(self):
        mock_client = AsyncMock()
        chunks = [
            {"id": "abc-1", "vector": [0.1, 0.2], "payload": {"article_number": "Article 1"}},
            {"id": "abc-2", "vector": [0.3, 0.4], "payload": {"article_number": "Article 2"}},
        ]

        with (
            patch("app.infrastructure.qdrant_client.get_settings", return_value=_settings()),
            patch("app.infrastructure.qdrant_client.get_qdrant_client", return_value=mock_client),
        ):
            await upsert_chunks(chunks)

        mock_client.upsert.assert_awaited_once()
        _, kwargs = mock_client.upsert.call_args
        assert kwargs["collection_name"] == "eu_ai_act"
        points = kwargs["points"]
        assert len(points) == 2
        assert points[0].id == "abc-1"
        assert points[0].vector == [0.1, 0.2]
        assert points[0].payload == {"article_number": "Article 1"}
