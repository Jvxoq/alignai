import logging

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url)


def search(query_vector: list[float], limit: int = 5) -> list[dict]:
    settings = get_settings()
    try:
        client = get_qdrant_client()
        results = client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vector,
            limit=limit,
        )
        return [
            {"id": str(hit.id), "score": hit.score, "payload": hit.payload or {}}
            for hit in results
        ]
    except Exception:
        logger.warning("Qdrant unavailable, returning stub results", exc_info=True)
        return [
            {
                "id": "stub-1",
                "score": 0.85,
                "payload": {"text": "Sample alignment guideline document."},
            }
        ]
