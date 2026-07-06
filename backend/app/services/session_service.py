import logging
from uuid import UUID

from fastapi import HTTPException, status
from app.models.user import ChatMessage

from app.core.config import get_settings
from app.infrastructure.database import (
    SessionRecord,
    count_sessions_for_user,
    create_session,
    delete_session,
    get_session_with_owner,
    get_sessions_for_user,
    increment_message_count,
    update_session_title as update_session_title_db,
)
from app.infrastructure.langgraph_client import get_langgraph_client

logger = logging.getLogger(__name__)

_LANGGRAPH_ROLE_MAP = {"human": "user", "ai": "assistant", "system": "system"}


def _normalize_role(role: str) -> str:
    return _LANGGRAPH_ROLE_MAP.get(role, role)


async def create_user_session(user_id: UUID) -> SessionRecord:
    settings = get_settings()
    existing = await count_sessions_for_user(user_id)
    if existing >= settings.MAX_SESSIONS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session limit reached ({settings.MAX_SESSIONS_PER_USER}). Delete an existing session to create a new one.",
        )
    return await create_session(user_id)


async def list_user_sessions(user_id: UUID, limit: int = 50, offset: int = 0) -> tuple[list[SessionRecord], int]:
    from app.infrastructure.database import count_sessions_for_user
    sessions = await get_sessions_for_user(user_id, limit, offset)
    total = await count_sessions_for_user(user_id)
    return sessions, total


async def delete_user_session(session_id: UUID, user_id: UUID) -> bool:
    deleted = await delete_session(session_id, user_id)
    if deleted:
        await delete_langgraph_thread(session_id)
    return deleted


async def increment_session_messages(session_id: UUID, user_id: UUID) -> SessionRecord:
    record = await increment_message_count(session_id, user_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied",
        )
    return record


async def check_message_threshold(record: SessionRecord) -> None:
    settings = get_settings()
    if record.message_count >= settings.USER_MESSAGE_THRESHOLD:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Message threshold exceeded for this session",
        )


async def validate_session_ownership(session_id: UUID, user_id: UUID) -> SessionRecord:
    record = await get_session_with_owner(session_id, user_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied",
        )
    return record


async def update_session_title(session_id: UUID, user_id: UUID, title: str) -> SessionRecord:
    record = await update_session_title_db(session_id, user_id, title)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied",
        )
    return record


async def get_session_messages(session_id: UUID, user_id: UUID) -> list[ChatMessage]:
    await validate_session_ownership(session_id, user_id)
    client = get_langgraph_client()
    try:
        state = await client.threads.get_state(str(session_id))
    except Exception:
        logger.warning("Could not retrieve LangGraph state for session %s", session_id)
        return []
    thread_values = state["values"]
    if isinstance(thread_values, list):
        result = []
        for msg in thread_values:
            if isinstance(msg, dict):
                role = _normalize_role(str(msg.get("type", "")) or str(msg.get("role", "")))
                content = str(msg.get("content", ""))
            else:
                role = _normalize_role(str(getattr(msg, "type", "")) or "")
                content = str(getattr(msg, "content", ""))
            if role and content:
                result.append(ChatMessage(role=role, content=content))
        return result
    elif isinstance(thread_values, dict):
        messages = thread_values.get("messages", [])
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                role = _normalize_role(str(msg.get("type", "")) or str(msg.get("role", "")))
                content = str(msg.get("content", ""))
            else:
                role = _normalize_role(str(getattr(msg, "type", "")) or "")
                content = str(getattr(msg, "content", ""))
            if role and content:
                result.append(ChatMessage(role=role, content=content))
        return result
    return []


async def delete_langgraph_thread(session_id: UUID) -> None:
    client = get_langgraph_client()
    try:
        await client.threads.delete(str(session_id))
    except Exception:
        logger.warning("Could not delete LangGraph thread for session %s", session_id)
