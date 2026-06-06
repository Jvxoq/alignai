import logging
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.infrastructure.database import get_session, upsert_session

logger = logging.getLogger(__name__)


async def create_or_update_session(session_id: str | None) -> str:
    resolved_id = UUID(session_id) if session_id else uuid4()
    try:
        record = await get_session(resolved_id)
        count = (record.message_count + 1) if record else 1
        await upsert_session(resolved_id, count)
    except Exception:
        logger.warning("Database unavailable, using in-memory session stub", exc_info=True)
    return str(resolved_id)


async def check_message_threshold(session_id: str) -> bool:
    settings = get_settings()
    try:
        record = await get_session(UUID(session_id))
        if record is None:
            return True
        return record.message_count < settings.message_threshold
    except Exception:
        logger.warning("Database unavailable, allowing request", exc_info=True)
        return True
