import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    if settings.qdrant_api_key:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection(client: QdrantClient) -> None:
    settings = get_settings()
    name = settings.qdrant_collection

    if client.collection_exists(name):
        logger.info("Qdrant collection %s already exists", name)
        return

    logger.info("Creating Qdrant collection %s (size=3072, cosine, m=16, ef_construct=200)", name)
    client.create_collection(
        collection_name=name,
        vectors_config=qmodels.VectorParams(
            size=3072,
            distance=qmodels.Distance.COSINE,
        ),
        hnsw_config=qmodels.HnswConfigDiff(
            m=16,
            ef_construct=200,
        ),
    )

    client.create_payload_index(
        collection_name=name,
        field_name="article_number",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=name,
        field_name="chapter_number",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=name,
        field_name="section_number",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=name,
        field_name="is_recital",
        field_schema=qmodels.PayloadSchemaType.BOOL,
    )
    client.create_payload_index(
        collection_name=name,
        field_name="recital_number",
        field_schema=qmodels.PayloadSchemaType.INTEGER,
    )
    logger.info("Payload indexes created for %s", name)


def search(query_vector: list[float], top_k: int | None = None) -> list[dict]:
    settings = get_settings()
    limit = top_k if top_k is not None else settings.retrieval_top_k
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


def upsert_chunks(client: QdrantClient, chunks: list[dict[str, Any]]) -> None:
    settings = get_settings()
    if not chunks:
        return

    points = [
        qmodels.PointStruct(
            id=chunk["id"],
            vector=chunk["vector"],
            payload=chunk["payload"],
        )
        for chunk in chunks
    ]

    client.upsert(
        collection_name=settings.qdrant_collection,
        points=points,
    )
