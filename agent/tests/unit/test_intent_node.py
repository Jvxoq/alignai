from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
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

    @patch("app.nodes.intent_node.get_settings")
    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_uses_intent_llm_model_from_settings(self, mock_llm, mock_get_settings):
        mock_get_settings.return_value = SimpleNamespace(INTENT_LLM_MODEL="llama-3.1-8b-instant")
        mock_llm.return_value = IntentClassification(objective="x", response=None)
        state = {
            "messages": [HumanMessage(content="What are the AI Act requirements?")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        await intent_node(state)
        _, kwargs = mock_llm.call_args
        assert kwargs["model"] == "llama-3.1-8b-instant"

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

    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_empty_llm_response_falls_back_to_keywords(self, mock_llm):
        mock_llm.return_value = IntentClassification(objective=None, response=None)
        state = {
            "messages": [HumanMessage(content="AI Act compliance question")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is not None
        assert "Retrieve EU AI Act provisions" in result["objective"]

    @pytest.mark.parametrize("exc", [TimeoutError("timed out"), ConnectionError("network down")])
    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_network_failure_compliance_query_falls_back_to_keywords(self, mock_llm, exc):
        mock_llm.side_effect = exc
        state = {
            "messages": [HumanMessage(content="What is AI Act compliance?")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is not None
        assert "Retrieve EU AI Act provisions" in result["objective"]
        assert result["messages"] == []

    @pytest.mark.parametrize("exc", [TimeoutError("timed out"), ConnectionError("network down")])
    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_network_failure_general_chat_returns_error_message(self, mock_llm, exc):
        mock_llm.side_effect = exc
        state = {
            "messages": [HumanMessage(content="Hello there")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is None
        assert len(result["messages"]) == 1
        assert "currently unable to process" in result["messages"][0].content

    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_value_error_compliance_query_falls_back_to_keywords(self, mock_llm):
        mock_llm.side_effect = ValueError("bad structured output")
        state = {
            "messages": [HumanMessage(content="high-risk AI system requirements")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is not None
        assert "Retrieve EU AI Act provisions" in result["objective"]
        assert result["messages"] == []

    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_value_error_general_chat_returns_fallback_message(self, mock_llm):
        mock_llm.side_effect = ValueError("bad structured output")
        state = {
            "messages": [HumanMessage(content="What's the weather like?")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is None
        assert len(result["messages"]) == 1
        assert "compliance auditor" in result["messages"][0].content

    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_unexpected_error_compliance_query_falls_back_to_keywords(self, mock_llm):
        mock_llm.side_effect = KeyError("unexpected")
        state = {
            "messages": [HumanMessage(content="deployment obligations under the AI Act")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is not None
        assert "Retrieve EU AI Act provisions" in result["objective"]
        assert result["messages"] == []

    @patch("app.nodes.intent_node.call_llm_structured", new_callable=AsyncMock)
    async def test_unexpected_error_general_chat_returns_fallback_message(self, mock_llm):
        mock_llm.side_effect = KeyError("unexpected")
        state = {
            "messages": [HumanMessage(content="tell me a joke")],
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
        result = await intent_node(state)
        assert result["objective"] is None
        assert len(result["messages"]) == 1
        assert "compliance auditor" in result["messages"][0].content
