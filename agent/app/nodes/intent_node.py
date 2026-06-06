from app.graph.state import AgentState
from app.prompts.intent_prompt import INTENT_PROMPT


async def intent_node(state: AgentState) -> dict:
    feature_text = state.get("feature_text", "")
    intent = "alignment_audit" if len(feature_text) > 20 else "general_question"
    return {
        "intent": intent,
        "messages": [{"role": "system", "content": INTENT_PROMPT.format(feature_text=feature_text)}],
    }
