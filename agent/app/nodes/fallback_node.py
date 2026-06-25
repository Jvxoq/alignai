import logging

from langchain_core.messages import AIMessage

from app.graph.state import RESET_DOCS, AgentState

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = (
    "I am currently unable to retrieve relevant EU AI Act context for this query "
    "after multiple attempts. Please provide more detail about the specific "
    "compliance area you are asking about, or rephrase your question."
)


async def fallback_node(state: AgentState) -> dict:
    attempts = state.get("retrieval_attempts", 0)
    objective = state.get("objective", "unknown")
    logger.warning(
        "Fallback triggered after %d retrieval attempts (objective=%s)",
        attempts,
        objective,
    )

    return {
        "retrieved_docs": RESET_DOCS,
        "messages": [AIMessage(content=FALLBACK_MESSAGE)],
    }
