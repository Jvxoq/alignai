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
import sys
from pathlib import Path

from app.core.logging import setup_logging
from app.infrastructure.ingest import run_pipeline


def _upsert_to_qdrant(chunks: list[dict]) -> None:
    from app.infrastructure.embeddings import embed_all
    from app.infrastructure.qdrant_client import ensure_collection, get_qdrant_client, upsert_chunks

    client = get_qdrant_client()
    ensure_collection(client)

    texts = [c["text"] for c in chunks]
    vectors = asyncio.run(embed_all(texts))

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
        upsert_chunks(client, batch)
        print(f"Upserted {min(i + batch_size, len(points))}/{len(points)} points")

    print(f"Done — {len(points)} points upserted to Qdrant")


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
        print(f"Error: {args.source} does not exist", file=sys.stderr)
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
        print(f"Saved {len(chunks_data)} chunks to {args.output}")

    if args.upsert:
        _upsert_to_qdrant(chunks_data)
    elif not args.output:
        print(f"\n{'='*60}")
        print(f"Pipeline complete")
        print(f"{'='*60}")
        print(f"Markdown size:  {result.markdown_length:,} chars")
        print(f"Articles found: {result.total_articles}")
        print(f"Total chunks:   {result.total_chunks}")
        print(f"Time elapsed:   {result.elapsed_seconds:.1f}s")
        print(f"{'='*60}")

        if result.chunks:
            print(f"\nSample chunk:")
            sample = result.chunks[0]
            print(f"  article: {sample.article_number or 'recital'}")
            print(f"  title:   {sample.article_title or 'n/a'}")
            print(f"  chapter: {sample.chapter_number or 'n/a'}")
            print(f"  text:    {sample.text[:200]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
