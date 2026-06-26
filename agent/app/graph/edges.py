from typing import Literal

from app.graph.state import AgentState


def should_retrieve(state: AgentState) -> Literal["retrieve", "__end__"]:
    if state.get("objective"):
        return "retrieve"
    return "__end__"


def check_relevance(state: AgentState) -> Literal["generate", "rewrite_objective", "fallback"]:
    is_relevant = state.get("is_relevant")
    attempts = state.get("retrieval_attempts", 0)

    if is_relevant:
        return "generate"
    if attempts >= 3:
        return "fallback"
    return "rewrite_objective"
