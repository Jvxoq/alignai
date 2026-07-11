import asyncio
import logging

from app.core.config import get_settings
from app.graph.state import AgentState
from app.infrastructure.embeddings import embed_text
from app.infrastructure.qdrant_client import search_chunks

logger = logging.getLogger(__name__)


def filter_by_threshold(hits: list[dict], threshold: float) -> list[dict]:
    return [h for h in hits if h.get("score", 0.0) >= threshold]


def deduplicate_by_article(hits: list[dict]) -> list[dict]:
    best_by_key: dict[str, dict] = {}
    for hit in hits:
        payload = hit.get("payload", {})
        article_number = payload.get("article_number")
        recital_number = payload.get("recital_number")
        # Recitals have no article_number -- key them by recital_number instead
        # of dropping them, otherwise a recital-only match dedups to nothing.
        key = article_number or (f"recital-{recital_number}" if recital_number else None)
        if not key:
            continue
        if key not in best_by_key or hit.get("score", 0.0) > best_by_key[key].get("score", 0.0):
            best_by_key[key] = hit
    return list(best_by_key.values())


def format_retrieved_docs(hits: list[dict]) -> list[dict]:
    docs = []
    for hit in hits:
        payload = hit.get("payload", {})
        docs.append({
            "article_number": payload.get("article_number"),
            "article_title": payload.get("article_title"),
            "chapter_number": payload.get("chapter_number"),
            "section_number": payload.get("section_number"),
            "recital_number": payload.get("recital_number"),
            "is_recital": payload.get("is_recital", False),
            "parent_text": payload.get("parent_text"),
            "similarity_score": hit.get("score", 0.0),
        })
    return docs


async def retriever_node(state: AgentState) -> dict:
    settings = get_settings()
    objective = state.get("objective")
    attempts = state.get("retrieval_attempts", 0) + 1

    if not objective:
        logger.warning("Retriever called without objective")
        return {
            "retrieval_attempts": attempts,
            "is_relevant": False,
            "retrieved_docs": [],
        }

    logger.info("Retrieval attempt %d for objective: %s", attempts, objective)

    try:
        async with asyncio.timeout(30):
            vector = await embed_text(objective, task_type="RETRIEVAL_QUERY")
            raw_hits = await search_chunks(vector, top_k=settings.RETRIEVAL_TOP_K)
    except asyncio.TimeoutError:
        logger.error("Retrieval timed out after 30s for objective: %s", objective)
        return {
            "retrieval_attempts": attempts,
            "is_relevant": False,
            "retrieved_docs": [],
        }
    except ConnectionError as e:
        logger.error("Retrieval failed due to connection error: %s", str(e))
        return {
            "retrieval_attempts": attempts,
            "is_relevant": False,
            "retrieved_docs": [],
        }
    except Exception as e:
        logger.exception("Unexpected error during retrieval: %s", type(e).__name__)
        return {
            "retrieval_attempts": attempts,
            "is_relevant": False,
            "retrieved_docs": [],
        }

    filtered = filter_by_threshold(raw_hits, settings.SIMILARITY_THRESHOLD)
    logger.debug(
        "Top-k scores: %s",
        [round(h.get("score", 0.0), 3) for h in raw_hits],
    )

    if not filtered:
        logger.info(
            "is_relevant=False (chunks_passed=0) on attempt %d", attempts
        )
        return {
            "retrieval_attempts": attempts,
            "is_relevant": False,
            "retrieved_docs": [],
        }

    unique = deduplicate_by_article(filtered)
    retrieved_docs = format_retrieved_docs(unique)

    logger.info(
        "is_relevant=True (chunks_passed=%d, unique_articles=%d) on attempt %d",
        len(filtered),
        len(unique),
        attempts,
    )

    return {
        "retrieval_attempts": attempts,
        "is_relevant": True,
        "retrieved_docs": retrieved_docs,
    }
