from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.core.utils import last_user_message
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
