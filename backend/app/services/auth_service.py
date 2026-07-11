import asyncio
import logging
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.infrastructure.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.infrastructure.database import create_user, delete_user, get_user_by_email, get_user_by_id
from app.models.user import TokenResponse
from app.services.session_service import delete_langgraph_thread, list_user_sessions

logger = logging.getLogger(__name__)

# Pre-computed hash verified against when an account does not exist, so the login
# path performs the same bcrypt work whether or not the email is registered.
# Without this, the missing-user branch returns measurably faster and lets an
# attacker enumerate valid emails by timing alone.
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-constant-time-login")


def _issue_tokens(user_id: UUID) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


async def signup(email: str, password: str) -> TokenResponse:
    if await get_user_by_email(email) is not None:
        logger.warning("Signup rejected: email already registered (%s)", email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    hashed = await asyncio.to_thread(hash_password, password)
    try:
        user = await create_user(email, hashed)
    except IntegrityError:
        # A concurrent signup won the race between the check above and this
        # insert; the unique constraint on email is the source of truth.
        logger.warning("Signup rejected on unique-constraint race (%s)", email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from None

    logger.info("User created: %s", user.id)
    # cast: SQLAlchemy's legacy Column attributes are typed as Column[UUID]
    # rather than UUID; the runtime value is a plain UUID.
    return _issue_tokens(cast(UUID, user.id))


async def login(email: str, password: str) -> TokenResponse:
    user = await get_user_by_email(email)
    stored_hash = cast(str, user.hashed_password) if user is not None else _DUMMY_PASSWORD_HASH
    password_valid = await asyncio.to_thread(verify_password, password, stored_hash)

    if user is None or not password_valid:
        logger.warning("Login failed: invalid credentials (%s)", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        logger.warning("Login failed: account deactivated (%s)", email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return _issue_tokens(cast(UUID, user.id))


async def refresh(refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        logger.warning("Refresh failed: token could not be decoded")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None

    if payload.get("type") != "refresh":
        logger.warning("Refresh failed: wrong token type (%s)", payload.get("type"))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError, TypeError):
        # A validly signed token can still carry a missing or malformed subject;
        # treat it as an invalid token rather than letting it raise a 500.
        logger.warning("Refresh failed: missing or malformed subject claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None

    user = await get_user_by_id(user_id)
    if user is None or not user.is_active:
        logger.warning("Refresh failed: user not found or inactive (%s)", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return _issue_tokens(user_id)


async def delete_user_account(user_id: UUID) -> bool:
    # The DB row cascade-deletes `sessions`, but that cascade has no idea
    # LangGraph threads exist -- clean those up first, while we still have
    # the session ids to do it with.
    sessions, _ = await list_user_sessions(user_id)
    for session in sessions:
        await delete_langgraph_thread(session.id)

    deleted = await delete_user(user_id)
    if deleted:
        logger.info("User account deleted: %s", user_id)
    return deleted
