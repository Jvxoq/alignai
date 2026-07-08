from pathlib import Path
from unittest.mock import patch

from app.infrastructure.ingest import (
    CHUNK_OVERLAP_TOKENS,
    _approx_tokens,
    _chunk_text,
    _is_page_artifact,
    _parse_markdown,
    convert_to_markdown,
    parse_and_chunk,
    run_pipeline,
)

SAMPLE_MD = """\
- (1) Whereas AI should be human-centric and trustworthy.
- ([1]) Some footnote reference that should be skipped.
- (2) Whereas transparency obligations matter.
continuation line for recital 2.
## CHAPTER I
GENERAL PROVISIONS
3/144
EN
OJ L, 2024/1689
ELI: http://data.europa.eu/eli/reg/2024/1689/oj
## _SECTION 1_
## _Article 1_
## **Subject matter**
This Regulation lays down harmonised rules.
It applies to providers and deployers.
## _Article 2_
**Scope**
This Article defines the scope of application.
## _ANNEX I_
Annex list content that should not become an article.
"""


class TestApproxTokens:
    def test_floor_of_one(self):
        assert _approx_tokens("") == 1
        assert _approx_tokens("hi") == 1

    def test_scales_with_length(self):
        assert _approx_tokens("a" * 40) == 10


class TestIsPageArtifact:
    def test_page_footer(self):
        assert _is_page_artifact("3/144") is True

    def test_lang_line(self):
        assert _is_page_artifact("EN") is True

    def test_oj_line(self):
        assert _is_page_artifact("OJ L, 2024/1689") is True

    def test_eli_line(self):
        assert _is_page_artifact("ELI: http://data.europa.eu/eli/reg/2024/1689/oj") is True

    def test_normal_text_is_not_artifact(self):
        assert _is_page_artifact("This Regulation lays down harmonised rules.") is False


class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        text = "A short article body."
        assert _chunk_text(text) == [text]

    def test_long_text_is_split_with_overlap(self):
        words = [f"w{i}" for i in range(1000)]
        text = " ".join(words)

        chunks = _chunk_text(text)

        assert len(chunks) > 1
        assert chunks[0].split()[0] == "w0"
        assert chunks[-1].split()[-1] == "w999"

        first_words = chunks[0].split()
        second_words = chunks[1].split()
        overlap = set(first_words[-CHUNK_OVERLAP_TOKENS:]) & set(second_words[:CHUNK_OVERLAP_TOKENS])
        assert len(overlap) > 0

    def test_text_under_token_target_is_single_chunk(self):
        text = "w " * 1000  # 2000 chars -> ~500 approx tokens, under the 512 target
        assert len(_chunk_text(text)) == 1


class TestParseMarkdown:
    def test_full_document_structure(self):
        chunks = _parse_markdown(SAMPLE_MD)

        recitals = [c for c in chunks if c.is_recital]
        articles = [c for c in chunks if c.article_number]

        assert len(recitals) == 2
        assert len(articles) == 2

    def test_footnote_lines_are_excluded_from_recitals(self):
        chunks = _parse_markdown(SAMPLE_MD)
        recitals = [c for c in chunks if c.is_recital]
        assert not any("footnote" in c.text for c in recitals)

    def test_recital_numbers_and_continuation(self):
        chunks = _parse_markdown(SAMPLE_MD)
        recitals = {c.recital_number: c for c in chunks if c.is_recital}

        assert set(recitals.keys()) == {1, 2}
        assert "continuation line for recital 2" in recitals[2].text

    def test_page_artifacts_do_not_leak_into_chapter_body(self):
        chunks = _parse_markdown(SAMPLE_MD)
        for chunk in chunks:
            assert "3/144" not in chunk.text
            assert "ELI:" not in chunk.text

    def test_article_metadata_and_title_from_heading_style(self):
        chunks = _parse_markdown(SAMPLE_MD)
        article1 = next(c for c in chunks if c.article_number == "Article 1")

        assert article1.article_title == "Subject matter"
        assert article1.chapter_number == "I"
        assert article1.section_number == "1"
        assert "harmonised rules" in article1.parent_text
        assert "providers and deployers" in article1.parent_text

    def test_article_title_from_standalone_bold_style(self):
        chunks = _parse_markdown(SAMPLE_MD)
        article2 = next(c for c in chunks if c.article_number == "Article 2")

        assert article2.article_title == "Scope"
        assert "scope of application" in article2.parent_text

    def test_annex_heading_closes_the_preceding_article_without_becoming_one(self):
        chunks = _parse_markdown(SAMPLE_MD)
        assert all(c.article_number != "Annex I" for c in chunks)
        assert not any("Annex list content" in c.text for c in chunks)

    def test_empty_input_yields_no_chunks(self):
        assert _parse_markdown("") == []

    def test_article_without_body_is_dropped(self):
        md = "## _Article 9_\n## **Empty Article**\n"
        assert _parse_markdown(md) == []


class TestConvertToMarkdown:
    def test_delegates_to_pymupdf4llm(self):
        with patch("app.infrastructure.ingest.pymupdf4llm") as mock_pymupdf:
            mock_pymupdf.to_markdown.return_value = "# converted"
            result = convert_to_markdown(Path("regulation.pdf"), pages=[0, 1])

        assert result == "# converted"
        mock_pymupdf.to_markdown.assert_called_once_with(
            "regulation.pdf", pages=[0, 1], show_progress=False
        )


class TestParseAndChunk:
    def test_returns_chunks_from_markdown(self):
        chunks = parse_and_chunk(SAMPLE_MD)
        assert len(chunks) == 4


class TestRunPipeline:
    def test_full_pipeline_end_to_end(self):
        with patch("app.infrastructure.ingest.pymupdf4llm") as mock_pymupdf:
            mock_pymupdf.to_markdown.return_value = SAMPLE_MD
            result = run_pipeline(Path("regulation.pdf"))

        assert result.markdown_length == len(SAMPLE_MD)
        assert result.total_articles == 2
        assert result.total_chunks == 4
        assert result.elapsed_seconds >= 0
        assert len(result.chunks) == 4
