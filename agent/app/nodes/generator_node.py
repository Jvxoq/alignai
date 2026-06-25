import logging

from langchain_core.messages import AIMessage

from app.core.utils import last_user_message
from app.graph.state import RESET_DOCS, AgentState
from app.infrastructure.llm_client import call_llm
from app.prompts.generator_prompt import GENERATOR_PROMPT

logger = logging.getLogger(__name__)

_FALLBACK_REPORT = (
    "# Compliance Audit Report\n\n"
    "## 1. Compliance Objective\n"
    "Insufficient information to determine.\n\n"
    "## 2. Relevant EU AI Act Articles\n"
    "- Insufficient information to determine.\n\n"
    "## 3. Assessment\n"
    "**Verdict:** Requires Further Review\n\n"
    "## 4. Findings\n"
    "- Insufficient information to determine.\n\n"
    "## 5. Recommendations\n"
    "- Review each cited article against the specific feature implementation.\n"
    "- Document compliance evidence for each requirement.\n"
)


def _format_context(docs: list[dict]) -> str:
    if not docs:
        return "No retrieved context."
    blocks: list[str] = []
    for doc in docs:
        article = doc.get("article_number", "Unknown Article")
        title = doc.get("article_title", "")
        chapter = doc.get("chapter_number", "")
        recital = doc.get("recital_number")
        is_recital = doc.get("is_recital", False)
        parent_text = doc.get("parent_text", "")

        header_parts: list[str] = []
        if is_recital and recital:
            header_parts.append(f"Recital {recital}")
        elif article:
            label = f"Article {article}"
            if title:
                label += f" — {title}"
            header_parts.append(label)
        if chapter:
            header_parts.append(f"Chapter {chapter}")

        header = " — ".join(header_parts) if header_parts else "Unknown"
        blocks.append(f"[{header}]\n{parent_text or 'No text available.'}")
    return "\n\n".join(blocks)


async def generator_node(state: AgentState) -> dict:
    objective = state.get("objective", "")
    docs = state.get("retrieved_docs", [])
    user_query = last_user_message(state.get("messages", []))

    context = _format_context(docs)

    try:
        prompt = GENERATOR_PROMPT.format(
            objective=objective,
            user_query=user_query,
            retrieved_docs=context,
        )
        report = await call_llm(prompt)
        logger.info("Compliance report generated via LLM for objective: %s", objective)
    except (TimeoutError, ConnectionError) as e:
        logger.error("LLM generation failed due to %s, using fallback report", type(e).__name__)
        report = _FALLBACK_REPORT
    except ValueError as e:
        logger.warning("LLM returned invalid report: %s, using fallback", str(e))
        report = _FALLBACK_REPORT
    except Exception as e:
        logger.exception("Unexpected error in report generation: %s", type(e).__name__)
        report = _FALLBACK_REPORT

    return {
        "retrieved_docs": RESET_DOCS,
        "messages": [AIMessage(content=report)],
    }
