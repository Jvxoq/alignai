from langchain_core.messages import AIMessage

from app.graph.state import RESET_DOCS
from app.nodes.fallback_node import fallback_node


class TestFallbackNode:
    async def test_returns_fallback_message(self):
        state = {
            "retrieval_attempts": 3,
            "messages": [],
        }
        result = await fallback_node(state)
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)
        assert "unable to retrieve" in result["messages"][0].content.lower()

    async def test_clears_retrieved_docs(self):
        state = {
            "retrieval_attempts": 3,
            "retrieved_docs": [{"article_number": "1"}],
            "messages": [],
        }
        result = await fallback_node(state)
        assert result["retrieved_docs"] is RESET_DOCS
