import logging

from langchain_core.messages import AIMessage

from app.core.utils import last_user_message
from app.graph.state import RESET_DOCS, AgentState
from app.infrastructure.llm_client import call_llm_structured
from app.models.intent import IntentClassification
from app.prompts.intent_prompt import INTENT_PROMPT

logger = logging.getLogger(__name__)

_FALLBACK_MESSAGE = (
    "I am a compliance auditor focused on the EU AI Act. "
    "Please ask a question related to AI Act compliance, "
    "high-risk classification, transparency obligations, or related regulatory topics."
)

_ERROR_MESSAGE = (
    "I am currently unable to process your request. "
    "Please try rephrasing."
)

_COMPLIANCE_KEYWORDS = (
    "ai act",
    "compliance",
    "audit",
    "high-risk",
    "high risk",
    "regulation",
    "regulatory",
    "article",
    "annex",
    "deploy",
    "deployment",
    "biometric",
    "transparency",
    "risk classification",
)


def _is_compliance_related(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in _COMPLIANCE_KEYWORDS)


def _build_objective(user_query: str) -> str:
    return (
        "Retrieve EU AI Act provisions relevant to: "
        + user_query.strip()
    )


async def intent_node(state: AgentState) -> dict:
    messages = state.get("messages", [])
    user_query = last_user_message(messages)

    base_updates: dict = {
        "retrieved_docs": RESET_DOCS,
        "is_relevant": None,
        "retrieval_attempts": 0,
    }

    if not user_query:
        logger.warning("Intent node called with no user message")
        return {
            **base_updates,
            "objective": None,
            "messages": [AIMessage(content=_FALLBACK_MESSAGE)],
        }

    try:
        prompt = INTENT_PROMPT.format(user_query=user_query)
        result = await call_llm_structured(prompt, IntentClassification)

        if result.objective:
            logger.info("Intent classified: compliance-related (LLM)")
            return {**base_updates, "objective": result.objective, "messages": []}

        if result.response:
            logger.info("Intent classified: general (LLM)")
            return {
                **base_updates,
                "objective": None,
                "messages": [AIMessage(content=result.response)],
            }

        logger.warning("LLM returned no objective or response, falling back to keywords")
        raise ValueError("empty LLM response")

    except (TimeoutError, ConnectionError) as e:
        logger.error("LLM classification failed due to network issue: %s, falling back to keywords", type(e).__name__)
        if _is_compliance_related(user_query):
            return {
                **base_updates,
                "objective": _build_objective(user_query),
                "messages": [],
            }
        return {
            **base_updates,
            "objective": None,
            "messages": [AIMessage(content=_ERROR_MESSAGE)],
        }
    except ValueError as e:
        logger.warning("LLM returned invalid response: %s, falling back to keywords", str(e))
        if _is_compliance_related(user_query):
            return {
                **base_updates,
                "objective": _build_objective(user_query),
                "messages": [],
            }
        return {
            **base_updates,
            "objective": None,
            "messages": [AIMessage(content=_FALLBACK_MESSAGE)],
        }
    except Exception as e:
        logger.exception("Unexpected error in intent classification: %s", type(e).__name__)
        if _is_compliance_related(user_query):
            return {
                **base_updates,
                "objective": _build_objective(user_query),
                "messages": [],
            }
        return {
            **base_updates,
            "objective": None,
            "messages": [AIMessage(content=_FALLBACK_MESSAGE)],
        }
