from typing import Literal

from app.graph.state import AgentState

RELEVANCE_THRESHOLD = 0.5


def should_retrieve(state: AgentState) -> Literal["retrieve", "generate"]:
    intent = state.get("intent", "")
    if intent in ("alignment_audit", "feature_review"):
        return "retrieve"
    return "generate"


def check_relevance(state: AgentState) -> Literal["generate", "rewrite_objective", "fallback"]:
    score = state.get("relevance_score", 0.0)
    docs = state.get("retrieved_docs", [])

    if not docs:
        return "fallback"
    if score < RELEVANCE_THRESHOLD:
        return "rewrite_objective"
    return "generate"
