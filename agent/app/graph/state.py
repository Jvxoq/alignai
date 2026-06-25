from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class _ResetDocs:
    pass


RESET_DOCS = _ResetDocs()


def docs_reducer(current: list[dict], new: list[dict] | _ResetDocs) -> list[dict]:
    if isinstance(new, _ResetDocs):
        return []
    return current + list(new)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    objective: Optional[str]
    retrieved_docs: Annotated[list[dict], docs_reducer]
    is_relevant: Optional[bool]
    retrieval_attempts: int