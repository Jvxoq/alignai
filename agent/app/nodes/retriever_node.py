from app.graph.state import AgentState
from app.infrastructure.embeddings import embed_text
from app.infrastructure.qdrant_client import search


async def retriever_node(state: AgentState) -> dict:
    feature_text = state.get("feature_text", "")
    vector = embed_text(feature_text, task_type="RETRIEVAL_QUERY")
    docs = search(vector)
    top_score = docs[0]["score"] if docs else 0.0
    return {"retrieved_docs": docs, "relevance_score": top_score}
