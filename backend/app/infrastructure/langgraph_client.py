import logging
from functools import lru_cache

from langgraph_sdk.client import get_client

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_langgraph_client():
    settings = get_settings()
    return get_client(
        url=settings.LANGGRAPH_SERVER_URL,
        timeout=(
            settings.LANGGRAPH_CONNECTION_TIMEOUT,
            settings.LANGGRAPH_READ_TIMEOUT,
            settings.LANGGRAPH_READ_TIMEOUT,
            settings.LANGGRAPH_CONNECTION_TIMEOUT,
        ),
    )
