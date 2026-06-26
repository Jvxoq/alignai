"""
CLI for testing retrieval against the live Qdrant collection.

Usage:
    python retrieve.py -q "What are the obligations for high-risk AI systems?"
    python retrieve.py -q "..." --top-k 5
    python retrieve.py -q "..." --raw           # skip the similarity threshold filter
    python retrieve.py                          # interactive prompt
"""

import argparse
import asyncio
import logging

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.infrastructure.embeddings import embed_text
from app.infrastructure.qdrant_client import search_chunks
from app.nodes.retriever_node import filter_by_threshold, deduplicate_by_article

logger = logging.getLogger(__name__)

QUIET_LOGGERS = ("httpx", "httpcore", "groq", "urllib3", "openai", "qdrant_client")


def _quiet_noisy_loggers() -> None:
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


async def retrieve(query: str, top_k: int | None, raw: bool) -> None:
    settings = get_settings()

    vector = await embed_text(query, task_type="RETRIEVAL_QUERY")
    hits = await search_chunks(vector, top_k=top_k or settings.RETRIEVAL_TOP_K)

    if not raw:
        hits = filter_by_threshold(hits, settings.SIMILARITY_THRESHOLD)
        hits = deduplicate_by_article(hits)

    if not hits:
        logger.info("No chunks passed threshold=%s (use --raw to bypass)", settings.SIMILARITY_THRESHOLD)
        return

    for hit in hits:
        payload = hit.get("payload", {})
        label = (
            f"Article {payload['article_number']}"
            if payload.get("article_number")
            else f"Recital {payload.get('recital_number')}"
        )
        text = payload.get("parent_text") or payload.get("text") or ""
        logger.info("[%.4f] %s\n%s", hit["score"], label, text[:500])


def main() -> None:
    setup_logging()
    _quiet_noisy_loggers()

    parser = argparse.ArgumentParser(description="Retrieve EU AI Act chunks for a query.")
    parser.add_argument("-q", "--query", type=str, help="Query text (omit for interactive prompt)")
    parser.add_argument("-k", "--top-k", type=int, default=None, help="Number of chunks to fetch")
    parser.add_argument("--raw", action="store_true", help="Skip threshold filter and dedup")
    args = parser.parse_args()

    query = args.query or input("> ")
    if not query.strip():
        logger.warning("Empty query — exiting")
        return

    asyncio.run(retrieve(query, args.top_k, args.raw))


if __name__ == "__main__":
    main()
