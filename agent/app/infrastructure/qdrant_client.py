import asyncio
import logging
from functools import lru_cache
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_qdrant_client() -> AsyncQdrantClient:
    settings = get_settings()
    return AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        timeout=30,
    )


async def ensure_collection() -> None:
    settings = get_settings()
    client = get_qdrant_client()
    name = settings.QDRANT_COLLECTION_NAME

    if await client.collection_exists(name):
        logger.info("Qdrant collection %s already exists", name)
        return

    logger.info(
        "Creating Qdrant collection %s (size=%d, cosine, m=16, ef_construct=200)",
        name,
        settings.EMBEDDING_DIMENSIONS,
    )
    await client.create_collection(
        collection_name=name,
        vectors_config=qmodels.VectorParams(
            size=settings.EMBEDDING_DIMENSIONS,
            distance=qmodels.Distance.COSINE,
        ),
        hnsw_config=qmodels.HnswConfigDiff(
            m=16,
            ef_construct=200,
        ),
    )

    await client.create_payload_index(
        collection_name=name,
        field_name="article_number",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    await client.create_payload_index(
        collection_name=name,
        field_name="chapter_number",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    await client.create_payload_index(
        collection_name=name,
        field_name="section_number",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    await client.create_payload_index(
        collection_name=name,
        field_name="is_recital",
        field_schema=qmodels.PayloadSchemaType.BOOL,
    )
    await client.create_payload_index(
        collection_name=name,
        field_name="recital_number",
        field_schema=qmodels.PayloadSchemaType.INTEGER,
    )
    logger.info("Payload indexes created for %s", name)


async def search_chunks(
    query_vector: list[float],
    top_k: int | None = None,
    filters: qmodels.Filter | None = None,
) -> list[dict]:
    settings = get_settings()
    client = get_qdrant_client()
    limit = top_k if top_k is not None else settings.RETRIEVAL_TOP_K
    async with asyncio.timeout(30):
        results = await client.query_points(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            query_filter=filters,
            with_payload=True,
        )
    return [
        {"id": str(point.id), "score": point.score, "payload": point.payload or {}}
        for point in results.points
    ]


async def upsert_chunks(chunks: list[dict[str, Any]]) -> None:
    settings = get_settings()
    client = get_qdrant_client()
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

    async with asyncio.timeout(60):
        await client.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=points,
        )
