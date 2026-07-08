"""
Ingestion pipeline: PDF → Markdown → Chunks.

Converts a PDF to markdown via pymupdf4llm, parses the structural hierarchy
(chapters → sections → articles → paragraphs) from markdown headings,
and chunks at paragraph level with configurable size and overlap.

Each chunk carries metadata: article_number, article_title, chapter_number,
section_number, page_number, parent_text (full article text for context).
"""

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf4llm

logger = logging.getLogger(__name__)

CHUNK_TARGET_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 50

ARTICLE_RE = re.compile(r"^##\s+_Article\s+(\d+[A-Za-z]?)_\s*$")
CHAPTER_RE = re.compile(r"^##\s+CHAPTER\s+([IVXLC]+)\b\s*(.*)$", re.IGNORECASE)
SECTION_RE = re.compile(r"^##\s+_SECTION\s+(\d+)_\s*$")
TITLE_RE = re.compile(r"^##\s+\*\*(.+?)\*\*\s*$")
STANDALONE_TITLE_RE = re.compile(r"^\*\*(.+?)\*\*\s*$")
ANNEX_RE = re.compile(r"^##\s+_ANNEX\s+([IVXLC]+)_\s*$", re.IGNORECASE)
RECITAL_RE = re.compile(r"^-\s*\((\d+)\)\s")
FOOTNOTE_RE = re.compile(r"^-\s*\(\[")

PAGE_FOOTER_RE = re.compile(r"^\d+/\d+\s*$")
LANG_LINE_RE = re.compile(r"^EN\s*$")
OJ_LINE_RE = re.compile(r"^OJ L,.*$")
ELI_RE = re.compile(r"^ELI:\s*http.*$")


@dataclass
class Chunk:
    id: str
    text: str
    article_number: str | None = None
    article_title: str | None = None
    chapter_number: str | None = None
    section_number: str | None = None
    is_recital: bool = False
    recital_number: int | None = None
    parent_text: str = ""


@dataclass
class PipelineResult:
    markdown_length: int = 0
    total_headings: int = 0
    total_articles: int = 0
    total_chunks: int = 0
    elapsed_seconds: float = 0.0
    chunks: list[Chunk] = field(default_factory=list)


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _is_page_artifact(line: str) -> bool:
    return bool(PAGE_FOOTER_RE.match(line) or LANG_LINE_RE.match(line)
            or OJ_LINE_RE.match(line) or ELI_RE.match(line))


def _chunk_text(text: str) -> list[str]:
    words = text.split()
    if _approx_tokens(text) <= CHUNK_TARGET_TOKENS:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_TARGET_TOKENS, len(words))
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - CHUNK_OVERLAP_TOKENS
    return chunks


def _parse_markdown(markdown: str) -> list[Chunk]:
    """Parse markdown into chunks by walking headings and grouping body text."""
    lines = markdown.split("\n")

    current_chapter_number: str | None = None
    current_section_number: str | None = None
    current_article_number: str | None = None
    current_article_title: str | None = None
    current_article_body_lines: list[str] = []
    all_chunks: list[Chunk] = []

    in_recitals = True
    current_recital_number: int | None = None
    current_recital_lines: list[str] = []

    def flush_article() -> None:
        nonlocal current_article_body_lines
        if not current_article_number or not current_article_body_lines:
            current_article_body_lines = []
            return

        body = "\n\n".join(current_article_body_lines)
        text_chunks = _chunk_text(body)

        for chunk_text in text_chunks:
            all_chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=chunk_text,
                article_number=f"Article {current_article_number}",
                article_title=current_article_title,
                chapter_number=current_chapter_number,
                section_number=current_section_number,
                parent_text=body,
            ))

        current_article_body_lines = []

    def flush_single_recital() -> None:
        nonlocal current_recital_lines
        if current_recital_number is None or not current_recital_lines:
            current_recital_lines = []
            return
        body = "\n\n".join(current_recital_lines)
        text_chunks = _chunk_text(body)
        for chunk_text in text_chunks:
            all_chunks.append(Chunk(
                id=str(uuid.uuid4()),
                text=chunk_text,
                is_recital=True,
                recital_number=current_recital_number,
            ))
        current_recital_lines = []

    for line in lines:
        stripped = line.strip()

        if _is_page_artifact(stripped):
            continue

        # Chapter heading
        m = CHAPTER_RE.match(stripped)
        if m:
            if in_recitals and current_recital_number is not None:
                flush_single_recital()
            elif current_article_number:
                flush_article()

            in_recitals = False
            current_chapter_number = m.group(1)
            current_section_number = None
            current_article_number = None
            current_article_title = None
            continue

        # Section heading
        m = SECTION_RE.match(stripped)
        if m:
            if current_article_number:
                flush_article()
            current_section_number = m.group(1)
            current_article_number = None
            current_article_title = None
            continue

        # Article number heading
        m = ARTICLE_RE.match(stripped)
        if m:
            if in_recitals and current_recital_number is not None:
                flush_single_recital()
            elif current_article_number:
                flush_article()

            current_article_number = m.group(1)
            current_article_title = None
            continue

        # Annex heading
        m = ANNEX_RE.match(stripped)
        if m:
            if in_recitals and current_recital_number is not None:
                flush_single_recital()
            elif current_article_number:
                flush_article()
            in_recitals = False
            current_article_number = None
            current_article_title = None
            continue

        # Bold title (follows article number)
        m = TITLE_RE.match(stripped) or STANDALONE_TITLE_RE.match(stripped)
        if m:
            if current_article_number and not current_article_title:
                current_article_title = m.group(1).strip()
            continue

        # Body text
        if not stripped:
            continue

        if in_recitals:
            # Skip footnotes
            if FOOTNOTE_RE.match(stripped):
                continue
            # Detect new recital boundary
            m = RECITAL_RE.match(stripped)
            if m:
                if current_recital_number is not None:
                    flush_single_recital()
                current_recital_number = int(m.group(1))
                current_recital_lines = [stripped]
            else:
                # Continuation line (page break wrapping) — accumulate
                if current_recital_number is not None:
                    current_recital_lines.append(stripped)
        elif current_article_number:
            current_article_body_lines.append(stripped)

    # Flush remaining
    if in_recitals and current_recital_number is not None:
        flush_single_recital()
    if current_article_number:
        flush_article()

    return all_chunks


def convert_to_markdown(pdf_path: Path, pages: list[int] | None = None) -> str:
    """Step 1: Convert PDF to markdown using pymupdf4llm."""
    logger.info("Converting PDF to markdown: %s", pdf_path)
    start = time.time()

    md = pymupdf4llm.to_markdown(
        str(pdf_path),
        pages=pages,
        show_progress=False,
    )

    elapsed = time.time() - start
    logger.info(
        "Markdown conversion complete — %d chars, %.1fs",
        len(md),
        elapsed,
    )
    return md


def parse_and_chunk(markdown: str) -> list[Chunk]:
    """Step 2: Parse markdown headings and chunk into structured segments."""
    logger.info("Parsing markdown structure and chunking")
    start = time.time()

    chunks = _parse_markdown(markdown)

    articles = {c.article_number for c in chunks if c.article_number}
    recitals = {c.recital_number for c in chunks if c.is_recital and c.recital_number is not None}

    elapsed = time.time() - start
    logger.info(
        "Chunking complete — %d chunks (%d articles, %d recitals), %.1fs",
        len(chunks),
        len(articles),
        len(recitals),
        elapsed,
    )
    return chunks


def run_pipeline(pdf_path: Path, pages: list[int] | None = None) -> PipelineResult:
    """Run the full ingestion pipeline: PDF → markdown → chunks."""
    pipeline_start = time.time()
    logger.info("Starting ingestion pipeline: %s", pdf_path)

    # Step 1: PDF → Markdown
    markdown = convert_to_markdown(pdf_path, pages)

    # Step 2: Markdown → Chunks
    chunks = parse_and_chunk(markdown)

    total_elapsed = time.time() - pipeline_start
    articles = {c.article_number for c in chunks if c.article_number}

    result = PipelineResult(
        markdown_length=len(markdown),
        total_headings=0,
        total_articles=len(articles),
        total_chunks=len(chunks),
        elapsed_seconds=total_elapsed,
        chunks=chunks,
    )

    logger.info(
        "Pipeline complete — articles=%d chunks=%d elapsed=%.1fs",
        result.total_articles,
        result.total_chunks,
        result.elapsed_seconds,
    )

    return result
