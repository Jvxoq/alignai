from app.graph.state import AgentState
from app.prompts.generator_prompt import GENERATOR_PROMPT


async def generator_node(state: AgentState) -> dict:
    feature_text = state.get("feature_text", "")
    docs = state.get("retrieved_docs", [])
    context = "\n".join(d.get("payload", {}).get("text", "") for d in docs)
    report = (
        f"## Alignment Report\n\n"
        f"**Feature:** {feature_text}\n\n"
        f"**Analysis:** Based on {len(docs)} retrieved document(s), "
        f"the feature shows reasonable alignment with established guidelines.\n\n"
        f"**Recommendations:**\n"
        f"- Add explicit acceptance criteria\n"
        f"- Document edge cases\n"
        f"- Define success metrics"
    )
    return {
        "report": report,
        "messages": [{"role": "assistant", "content": GENERATOR_PROMPT.format(feature_text=feature_text, context=context)}],
    }
