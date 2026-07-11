from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.graph.state import RESET_DOCS
from app.nodes.generator_node import _format_context, generator_node


class TestFormatContext:
    def test_empty_docs(self):
        assert _format_context([]) == "No retrieved context."

    def test_with_article(self):
        docs = [
            {
                "article_number": "6",
                "article_title": "Scope",
                "chapter_number": "II",
                "recital_number": None,
                "is_recital": False,
                "parent_text": "Article 6 text here.",
            }
        ]
        result = _format_context(docs)
        assert "Article 6" in result
        assert "Scope" in result
        assert "Chapter II" in result
        assert "Article 6 text here." in result

    def test_with_recital(self):
        docs = [
            {
                "article_number": None,
                "article_title": None,
                "chapter_number": None,
                "recital_number": 42,
                "is_recital": True,
                "parent_text": "Recital 42 text.",
            }
        ]
        result = _format_context(docs)
        assert "Recital 42" in result
        assert "Recital 42 text." in result

    def test_missing_parent_text(self):
        docs = [
            {
                "article_number": "5",
                "article_title": "Prohibited AI",
                "chapter_number": "II",
                "recital_number": None,
                "is_recital": False,
                "parent_text": None,
            }
        ]
        result = _format_context(docs)
        assert "No text available." in result

    def test_chapter_and_section_combined(self):
        docs = [
            {
                "article_number": "10",
                "article_title": None,
                "chapter_number": "III",
                "section_number": "2",
                "recital_number": None,
                "is_recital": False,
                "parent_text": "Data governance text.",
            }
        ]
        result = _format_context(docs)
        assert "Article 10" in result
        assert "Chapter III" in result
        assert "Section 2" in result

    def test_unknown_header_when_no_article_or_recital(self):
        docs = [
            {
                "article_number": None,
                "article_title": None,
                "chapter_number": None,
                "section_number": None,
                "recital_number": None,
                "is_recital": False,
                "parent_text": "Orphaned text.",
            }
        ]
        result = _format_context(docs)
        assert "[Unknown]" in result

    def test_multiple_docs_joined_with_blank_line(self):
        docs = [
            {
                "article_number": "1",
                "article_title": None,
                "chapter_number": None,
                "section_number": None,
                "recital_number": None,
                "is_recital": False,
                "parent_text": "First.",
            },
            {
                "article_number": "2",
                "article_title": None,
                "chapter_number": None,
                "section_number": None,
                "recital_number": None,
                "is_recital": False,
                "parent_text": "Second.",
            },
        ]
        result = _format_context(docs)
        assert result.count("\n\n") >= 1
        assert "First." in result and "Second." in result


class TestGeneratorNode:
    @patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock)
    async def test_generates_report(self, mock_llm):
        mock_llm.return_value = "# Compliance Audit Report\n\nTest report content"
        state = {
            "objective": "high-risk AI requirements",
            "retrieved_docs": [
                {
                    "article_number": "6",
                    "article_title": "Scope",
                    "chapter_number": "II",
                    "recital_number": None,
                    "is_recital": False,
                    "parent_text": "Article 6 text.",
                }
            ],
            "messages": [HumanMessage(content="What are the requirements?")],
        }
        result = await generator_node(state)
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)
        assert result["retrieved_docs"] is RESET_DOCS

    @patch("app.nodes.generator_node.get_settings")
    @patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock)
    async def test_uses_generator_llm_model_from_settings(self, mock_llm, mock_get_settings):
        mock_get_settings.return_value = SimpleNamespace(GENERATOR_LLM_MODEL="llama-guard-4-12b")
        mock_llm.return_value = "report"
        state = {
            "objective": "test",
            "retrieved_docs": [],
            "messages": [HumanMessage(content="x")],
        }
        await generator_node(state)
        _, kwargs = mock_llm.call_args
        assert kwargs["model"] == "llama-guard-4-12b"

    @patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock)
    async def test_llm_failure_uses_fallback(self, mock_llm):
        mock_llm.side_effect = RuntimeError("LLM unavailable")
        state = {
            "objective": "test",
            "retrieved_docs": [],
            "messages": [HumanMessage(content="test")],
        }
        result = await generator_node(state)
        assert len(result["messages"]) == 1
        assert "Compliance Audit Report" in result["messages"][0].content

    @pytest.mark.parametrize("exc", [TimeoutError("timed out"), ConnectionError("network down")])
    @patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock)
    async def test_network_failure_uses_fallback_report(self, mock_llm, exc):
        mock_llm.side_effect = exc
        state = {
            "objective": "test",
            "retrieved_docs": [],
            "messages": [HumanMessage(content="test")],
        }
        result = await generator_node(state)
        assert len(result["messages"]) == 1
        assert "Requires Further Review" in result["messages"][0].content

    @patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock)
    async def test_value_error_uses_fallback_report(self, mock_llm):
        mock_llm.side_effect = ValueError("invalid report format")
        state = {
            "objective": "test",
            "retrieved_docs": [],
            "messages": [HumanMessage(content="test")],
        }
        result = await generator_node(state)
        assert len(result["messages"]) == 1
        assert "Insufficient information to determine" in result["messages"][0].content

    @patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock)
    async def test_unexpected_error_uses_fallback_report(self, mock_llm):
        mock_llm.side_effect = KeyError("unexpected")
        state = {
            "objective": "test",
            "retrieved_docs": [],
            "messages": [HumanMessage(content="test")],
        }
        result = await generator_node(state)
        assert len(result["messages"]) == 1
        assert "Compliance Audit Report" in result["messages"][0].content

    @patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock)
    async def test_llm_failure_with_retrieved_docs_does_not_claim_insufficient_info(self, mock_llm):
        mock_llm.side_effect = RuntimeError("LLM unavailable")
        state = {
            "objective": "test",
            "retrieved_docs": [
                {"article_number": "6", "parent_text": "Article 6 text.", "is_recital": False}
            ],
            "messages": [HumanMessage(content="test")],
        }
        result = await generator_node(state)
        content = result["messages"][0].content
        assert "Insufficient information" not in content
        assert "Compliance Audit Report" in content

    @patch("app.nodes.generator_node.call_llm", new_callable=AsyncMock)
    async def test_clears_retrieved_docs(self, mock_llm):
        mock_llm.return_value = "Report"
        state = {
            "objective": "test",
            "retrieved_docs": [{"article_number": "1"}],
            "messages": [],
        }
        result = await generator_node(state)
        assert result["retrieved_docs"] is RESET_DOCS
