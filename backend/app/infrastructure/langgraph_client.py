from langgraph_sdk.client import get_client

from app.core.config import get_settings


def get_langgraph_client():
    settings = get_settings()
    return get_client(
        url=settings.langgraph_url,
        api_key=settings.langgraph_api_key or None,
    )
