from langchain_core.messages import HumanMessage


def last_user_message(messages: list) -> str:
    """Extract the content of the most recent user message from a message list.

    Handles both LangChain HumanMessage objects and plain dicts with role='user'.
    """
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
        if isinstance(msg, dict) and msg.get("role") == "user":
            return str(msg.get("content", ""))
    return ""
