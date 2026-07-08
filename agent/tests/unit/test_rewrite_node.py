from unittest.mock import AsyncMock, patch

from langchain_core.messages import HumanMessage

from app.models.rewrite import RewrittenObjective
from app.nodes.rewrite_objective_node import (
    _build_refined_objective,
    rewrite_objective_node,
)


class TestBuildRefinedObjective:
    def test_with_user_query(self):
        result = _build_refined_objective("original objective", "user query")
        assert "original objective" in result
        assert "user query" in result

    def test_without_user_query(self):
        result = _build_refined_objective("original objective", "")
        assert "original objective" in result
        assert "target exact EU AI Act" in result


class TestRewriteObjectiveNode:
    @patch("app.nodes.rewrite_objective_node.call_llm_structured", new_callable=AsyncMock)
    async def test_rewrites_objective(self, mock_llm):
        mock_llm.return_value = RewrittenObjective(objective="Rewritten objective for high-risk systems")
        state = {
            "objective": "original objective",
            "messages": [HumanMessage(content="user query")],
            "is_relevant": False,
            "retrieval_attempts": 1,
        }
        result = await rewrite_objective_node(state)
        assert result["objective"] == "Rewritten objective for high-risk systems"
        assert result["is_relevant"] is None

    @patch("app.nodes.rewrite_objective_node.call_llm_structured", new_callable=AsyncMock)
    async def test_llm_failure_falls_back(self, mock_llm):
        mock_llm.side_effect = RuntimeError("LLM unavailable")
        state = {
            "objective": "original",
            "messages": [HumanMessage(content="query")],
            "is_relevant": False,
            "retrieval_attempts": 1,
        }
        result = await rewrite_objective_node(state)
        assert "original" in result["objective"]
        assert result["is_relevant"] is None

    @patch("app.nodes.rewrite_objective_node.call_llm_structured", new_callable=AsyncMock)
    async def test_empty_llm_response_falls_back(self, mock_llm):
        mock_llm.return_value = RewrittenObjective(objective="")
        state = {
            "objective": "original",
            "messages": [HumanMessage(content="query")],
            "is_relevant": False,
            "retrieval_attempts": 1,
        }
        result = await rewrite_objective_node(state)
        assert "original" in result["objective"]
        assert result["is_relevant"] is None
