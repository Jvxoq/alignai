from langchain_core.messages import HumanMessage

from app.graph.graph import graph


async def test_graph_compiles_and_invokes():
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Hello")],
            "objective": None,
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
    )

    assert "messages" in result
    assert "objective" in result
    assert "retrieved_docs" in result
    assert "is_relevant" in result
    assert "retrieval_attempts" in result
    assert len(result["messages"]) > 0


async def test_graph_with_compliance_query():
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="What are the AI Act requirements?")],
            "objective": None,
            "retrieved_docs": [],
            "is_relevant": None,
            "retrieval_attempts": 0,
        }
    )

    assert "messages" in result
    assert "objective" in result
    assert isinstance(result.get("retrieval_attempts"), int)
