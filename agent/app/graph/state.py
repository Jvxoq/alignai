from typing import Annotated, TypedDict


def merge_lists(left: list, right: list) -> list:
    return left + right


class AgentState(TypedDict):
    messages: Annotated[list[dict], merge_lists]
    intent: str
    retrieved_docs: list[dict]
    feature_text: str
    report: str
    relevance_score: float
