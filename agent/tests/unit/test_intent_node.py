from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.core.utils import last_user_message
from app.graph.state import RESET_DOCS
from app.models.intent import IntentClassification
from app.nodes.intent_node import (
    _build_objective,
    _is_compliance_related,
    intent_node,
)


class TestLastUserMessage:
    def test_with_human_message(self):
        messages = [HumanMessage(content="What is the AI Act?")]
        assert last_user_message(messages) == "What is the AI Act?"

    def test_with_dict_message(self):
        messages = [{"role": "user", "content": "Hello"}]
        assert last_user_message(messages) == "Hello"

    def test_with_mixed_messages(self):
        messages = [
            AIMessage(content="Response"),
            HumanMessage(content="Question"),
        ]
        assert last_user_message(messages) == "Question"

    def test_empty_messages(self):
        assert last_user_message([]) == ""


class TestIsComplianceRelated:
    def test_compliance_keyword(self):
        assert _is_compliance_related("What is the AI Act compliance?") is True

    def test_high_risk_keyword(self):
        assert _is_compliance_related("high-risk AI systems") is True

    def test_general_topic(self):
        assert _is_compliance_related("What is the weather?") is False


class TestBuildObjective:
    def test_builds_objective(self):
        result = _build_objective("high-risk requirements")
        assert "Retrieve EU AI Act provisions" in result
        assert "high-risk requirements" in result


class TestIntentNode:
    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_compliance_query(self, mock_llm):
        mock_llm.return_value = IntentClassification(
            objective="test objective", response=None
        )
        state = {
            "messages": [HumanMessage(content="What are the AI Act requirements?")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] == "test objective"
        assert result["retrieved_docs"] is RESET_DOCS
        assert result["retrieval_attempts"] == 0

    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_general_chat(self, mock_llm):
        mock_llm.return_value = IntentClassification(
            objective=None, response="Hello! How can I help?"
        )
        state = {
            "messages": [HumanMessage(content="Hello")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is None
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

    async def test_empty_messages(self):
        state = {
            "messages": [],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is None
        assert len(result["messages"]) == 1

    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_llm_failure_falls_back_to_keywords(self, mock_llm):
        mock_llm.side_effect = RuntimeError("LLM unavailable")
        state = {
            "messages": [HumanMessage(content="What is AI Act compliance?")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is not None
        assert "Retrieve EU AI Act provisions" in result["objective"]

    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_llm_failure_general_chat(self, mock_llm):
        mock_llm.side_effect = RuntimeError("LLM unavailable")
        state = {
            "messages": [HumanMessage(content="Hello there")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is None
        assert len(result["messages"]) == 1
