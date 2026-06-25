import os

import pytest

from app.nodes.retriever_node import retriever_node

# Hits live Gemini + Qdrant. Opt in with RUN_LIVE_TESTS=1; mocked
# coverage lives in tests/unit/test_retriever_node.py.
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_TESTS") != "1",
    reason="live infra test; set RUN_LIVE_TESTS=1 to run",
)


@pytest.mark.asyncio
async def test_retriever_node_end_to_end():
    mock_state = {
        "objective": "What are the requirements for high-risk AI systems?",
        "retrieval_attempts": 0,
        "retrieved_docs": [],
        "is_relevant": None,
        "messages": [],
    }

    result = await retriever_node(mock_state)

    assert result["retrieval_attempts"] == 1
    assert result["is_relevant"] in [True, False]

    if result["is_relevant"]:
        assert len(result["retrieved_docs"]) > 0
        for doc in result["retrieved_docs"]:
            print(doc)
            assert "article_number" in doc
            assert "parent_text" in doc
            assert "similarity_score" in doc
            assert isinstance(doc["similarity_score"], float)
        print(f"Retrieved {len(result['retrieved_docs'])} unique articles")
        for doc in result["retrieved_docs"]:
            print(
                f"  Article {doc['article_number']} — score {doc['similarity_score']}"
            )
    else:
        print("No relevant documents found")


@pytest.mark.asyncio
async def test_retriever_node_empty_objective():
    mock_state = {
        "objective": "",
        "retrieval_attempts": 0,
        "retrieved_docs": [],
        "is_relevant": None,
        "messages": [],
    }

    result = await retriever_node(mock_state)

    assert result["retrieval_attempts"] == 1
    assert result["is_relevant"] is False
    assert result["retrieved_docs"] == []
