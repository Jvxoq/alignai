from app.graph.state import AgentState


async def fallback_node(state: AgentState) -> dict:
    return {
        "report": (
            "## Alignment Report\n\n"
            "Unable to retrieve relevant context for this feature description. "
            "Please provide more detail or try rephrasing your objective."
        ),
        "messages": [{"role": "assistant", "content": "Fallback response — no relevant context found."}],
    }
