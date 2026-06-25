"""
CLI wrapper for the ingestion pipeline.

Usage:
    python ingest.py --source ./data/eu_ai_act.pdf
    python ingest.py --source ./data/eu_ai_act.pdf --pages 1-10
    python ingest.py --source ./data/eu_ai_act.pdf --output ./data/chunks.json
    python ingest.py --source ./data/eu_ai_act.pdf --upsert
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from app.core.logging import setup_logging
from app.infrastructure.ingest import run_pipeline

logger = logging.getLogger(__name__)


async def _upsert_to_qdrant(chunks: list[dict]) -> None:
    from app.infrastructure.embeddings import embed_all
    from app.infrastructure.qdrant_client import ensure_collection, upsert_chunks

    await ensure_collection()

    texts = [c["text"] for c in chunks]
    vectors = await embed_all(texts)

    points = []
    for chunk, vector in zip(chunks, vectors):
        payload = {
            "article_number": chunk["article_number"],
            "article_title": chunk["article_title"],
            "chapter_number": chunk["chapter_number"],
            "section_number": chunk["section_number"],
            "is_recital": chunk["is_recital"],
            "recital_number": chunk["recital_number"],
        }
        if not chunk["is_recital"]:
            payload["parent_text"] = chunk["parent_text"]
            payload["text"] = chunk["text"]
        else:
            payload["text"] = chunk["text"]

        points.append({
            "id": chunk["id"],
            "vector": vector,
            "payload": payload,
        })

    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        await upsert_chunks(batch)
        logger.info("Upserted %d/%d points", min(i + batch_size, len(points)), len(points))

    logger.info("Done — %d points upserted to Qdrant", len(points))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest EU AI Act PDF into chunks")
    parser.add_argument("--source", type=Path, required=True, help="Path to source PDF")
    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help="Page range, e.g. '1-10' or '5' (default: all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: print summary)",
    )
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="Embed and upsert chunks to Qdrant after pipeline",
    )
    args = parser.parse_args()

    setup_logging()

    if not args.source.exists():
        logger.error("Source file does not exist: %s", args.source)
        return 1

    pages = None
    if args.pages:
        if "-" in args.pages:
            start, end = args.pages.split("-", 1)
            pages = list(range(int(start) - 1, int(end)))
        else:
            pages = [int(args.pages) - 1]

    result = run_pipeline(args.source, pages)

    chunks_data = [
        {
            "id": c.id,
            "text": c.text,
            "article_number": c.article_number,
            "article_title": c.article_title,
            "chapter_number": c.chapter_number,
            "section_number": c.section_number,
            "is_recital": c.is_recital,
            "recital_number": c.recital_number,
            "parent_text": c.parent_text if not c.is_recital else None,
        }
        for c in result.chunks
    ]

    if args.output:
        args.output.write_text(json.dumps(chunks_data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Saved %d chunks to %s", len(chunks_data), args.output)

    if args.upsert:
        asyncio.run(_upsert_to_qdrant(chunks_data))
    elif not args.output:
        logger.info(
            "Pipeline complete — articles=%d chunks=%d elapsed=%.1fs markdown_size=%d",
            result.total_articles,
            result.total_chunks,
            result.elapsed_seconds,
            result.markdown_length,
        )

        if result.chunks:
            sample = result.chunks[0]
            logger.info(
                "Sample chunk — article=%s title=%s chapter=%s text_preview=%s",
                sample.article_number or "recital",
                sample.article_title or "n/a",
                sample.chapter_number or "n/a",
                sample.text[:200],
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
