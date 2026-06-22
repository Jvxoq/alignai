import logging
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.auth import decode_token
from app.infrastructure.database import get_user_by_id
from app.models.requests import AlignRequest
from app.models.user import UserResponse
from app.services.session_service import (
    check_message_threshold,
    increment_session_messages,
    validate_session_ownership,
)

logger = logging.getLogger(__name__)

_BEARER_PREFIX = "Bearer "


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> UserResponse:
    if not authorization or not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    token = authorization[len(_BEARER_PREFIX):]
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    try:
        user_record = await get_user_by_id(user_id)
    except SQLAlchemyError:
        logger.exception("Database lookup failed while authenticating user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        )
    if user_record is None or not user_record.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return UserResponse.model_validate(user_record, from_attributes=True)


async def validate_session(
    body: AlignRequest,
    current_user: UserResponse = Depends(get_current_user),
) -> str:
    # NOTE: this body parameter must share its name with the `align` route's
    # body parameter so FastAPI dedups them into a single request body. The
    # route names its Starlette Request `request` (required by the slowapi
    # rate limiter), so the body is named `body` in both places.
    try:
        session_uuid = UUID(body.session_id)
        await validate_session_ownership(session_uuid, current_user.id)
        record = await increment_session_messages(session_uuid, current_user.id)
        await check_message_threshold(record)
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format",
        )
    except SQLAlchemyError:
        logger.exception("Database operation failed for session %s", body.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed",
        )
    return body.session_id
