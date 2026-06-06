from app.graph.state import AgentState
from app.prompts.rewrite_prompt import REWRITE_PROMPT


async def rewrite_objective_node(state: AgentState) -> dict:
    feature_text = state.get("feature_text", "")
    docs = state.get("retrieved_docs", [])
    context = "\n".join(d.get("payload", {}).get("text", "") for d in docs)
    refined = f"Audit alignment of: {feature_text}"
    return {
        "feature_text": refined,
        "messages": [{"role": "system", "content": REWRITE_PROMPT.format(feature_text=feature_text, context=context)}],
    }
