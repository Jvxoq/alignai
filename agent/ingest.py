"""
Standalone ingestion script — not part of the serving layer.

Usage:
    python ingest.py --source ./data/docs

Reads documents from the source directory, embeds them via Gemini,
and upserts vectors into the configured Qdrant collection.
"""

import argparse
import logging
import sys
from pathlib import Path

from app.core.logging import setup_logging
from app.infrastructure.embeddings import embed_text

logger = logging.getLogger(__name__)


def ingest(source: Path) -> int:
    if not source.exists():
        logger.error("Source path does not exist: %s", source)
        return 1

    files = list(source.glob("**/*.txt")) + list(source.glob("**/*.md"))
    if not files:
        logger.warning("No .txt or .md files found in %s", source)
        return 0

    logger.info("Found %d files to ingest (stub — no Qdrant upsert without credentials)", len(files))
    for path in files:
        text = path.read_text(encoding="utf-8")
        vector = embed_text(text, task_type="RETRIEVAL_DOCUMENT")
        logger.info("Embedded %s (%d dims)", path.name, len(vector))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest documents into Qdrant")
    parser.add_argument("--source", type=Path, required=True, help="Directory containing documents")
    args = parser.parse_args()

    setup_logging()
    return ingest(args.source)


if __name__ == "__main__":
    sys.exit(main())
