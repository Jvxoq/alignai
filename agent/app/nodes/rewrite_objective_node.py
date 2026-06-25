import logging

from app.core.utils import last_user_message
from app.graph.state import AgentState
from app.infrastructure.llm_client import call_llm
from app.prompts.rewrite_prompt import REWRITE_PROMPT

logger = logging.getLogger(__name__)


def _build_refined_objective(objective: str, user_query: str) -> str:
    if user_query:
        return (
            f"{objective} — focus on specific EU AI Act articles, "
            f"annexes, or provisions addressing: {user_query}"
        )
    return f"{objective} — target exact EU AI Act articles or annex provisions."


async def rewrite_objective_node(state: AgentState) -> dict:
    objective = state.get("objective") or ""
    messages = state.get("messages", [])
    user_query = last_user_message(messages)

    try:
        prompt = REWRITE_PROMPT.format(objective=objective, user_query=user_query)
        raw = await call_llm(prompt)
        refined = raw.strip().strip('"').strip("'")
        if refined:
            logger.info("Objective rewritten via LLM: '%s' -> '%s'", objective, refined)
            return {
                "objective": refined,
                "is_relevant": None,
            }
        logger.warning("LLM returned empty rewrite, falling back to string append")
        raise ValueError("empty LLM response")

    except Exception:
        logger.exception("LLM rewrite failed, falling back to string append")
        refined = _build_refined_objective(objective, user_query)
        return {
            "objective": refined,
            "is_relevant": None,
        }
