import pytest

from app.graph.graph import graph


@pytest.mark.asyncio
async def test_graph_compiles_and_invokes():
    result = await graph.ainvoke(
        {
            "messages": [],
            "intent": "",
            "retrieved_docs": [],
            "feature_text": "Build a user authentication system with OAuth2 support",
            "report": "",
            "relevance_score": 0.0,
        }
    )
    assert "report" in result
    assert len(result["report"]) > 0
    assert result["intent"] == "alignment_audit"
