from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_current_user, validate_session
from app.infrastructure.auth import create_access_token, create_refresh_token
from app.models.requests import AlignRequest
from app.models.user import UserResponse


def _user_record(is_active: bool = True):
    return SimpleNamespace(
        id=uuid4(),
        email="user@example.com",
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
    )


def _current_user() -> UserResponse:
    return UserResponse(
        id=uuid4(),
        email="user@example.com",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_missing_authorization_header_returns_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(authorization=None)
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid authorization header"

    @pytest.mark.asyncio
    async def test_non_bearer_scheme_returns_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(authorization="Basic abc123")
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid authorization header"

    @pytest.mark.asyncio
    async def test_undecodable_token_returns_401(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(authorization="Bearer not-a-jwt")
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid or expired token"

    @pytest.mark.asyncio
    async def test_wrong_token_type_returns_401(self):
        # A refresh token must not be accepted for authentication.
        token = create_refresh_token(uuid4())
        with pytest.raises(HTTPException) as exc:
            await get_current_user(authorization=f"Bearer {token}")
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid token type"

    @pytest.mark.asyncio
    async def test_malformed_subject_returns_401(self):
        with patch(
            "app.api.dependencies.decode_token",
            return_value={"sub": "not-a-uuid", "type": "access"},
        ):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(authorization="Bearer whatever")
        assert exc.value.status_code == 401
        assert exc.value.detail == "Invalid token payload"

    @pytest.mark.asyncio
    async def test_database_error_returns_500(self):
        # A DB outage during auth must surface as a clean, logged 500 rather
        # than an unhandled exception.
        token = create_access_token(uuid4())
        with patch(
            "app.api.dependencies.get_user_by_id",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("connection refused"),
        ):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(authorization=f"Bearer {token}")
        assert exc.value.status_code == 500
        assert exc.value.detail == "Database operation failed"

    @pytest.mark.asyncio
    async def test_unknown_user_returns_401(self):
        token = create_access_token(uuid4())
        with patch(
            "app.api.dependencies.get_user_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(authorization=f"Bearer {token}")
        assert exc.value.status_code == 401
        assert exc.value.detail == "User not found or inactive"

    @pytest.mark.asyncio
    async def test_inactive_user_returns_401(self):
        token = create_access_token(uuid4())
        with patch(
            "app.api.dependencies.get_user_by_id",
            new_callable=AsyncMock,
            return_value=_user_record(is_active=False),
        ):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(authorization=f"Bearer {token}")
        assert exc.value.status_code == 401
        assert exc.value.detail == "User not found or inactive"

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        record = _user_record()
        token = create_access_token(record.id)
        with patch(
            "app.api.dependencies.get_user_by_id",
            new_callable=AsyncMock,
            return_value=record,
        ):
            user = await get_current_user(authorization=f"Bearer {token}")
        assert isinstance(user, UserResponse)
        assert user.email == record.email
        assert user.id == record.id


class TestValidateSession:
    def _request(self, session_id: str | None = None) -> AlignRequest:
        return AlignRequest(session_id=session_id or str(uuid4()), user_message="hello")

    @pytest.mark.asyncio
    async def test_happy_path_returns_session_id(self):
        request = self._request()
        with (
            patch("app.api.dependencies.validate_session_ownership", new_callable=AsyncMock),
            patch(
                "app.api.dependencies.increment_session_messages",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(message_count=1),
            ),
        ):
            result = await validate_session(request, current_user=_current_user())
        assert result == request.session_id

    @pytest.mark.asyncio
    async def test_invalid_session_id_returns_400(self):
        # The ValueError branch: a value that slips past the model (assignment is
        # not re-validated) must become a 400, not a 500.
        request = self._request()
        request.session_id = "not-a-uuid"
        with pytest.raises(HTTPException) as exc:
            await validate_session(request, current_user=_current_user())
        assert exc.value.status_code == 400
        assert exc.value.detail == "Invalid session ID format"

    @pytest.mark.asyncio
    async def test_ownership_failure_propagates_404(self):
        request = self._request()
        with patch(
            "app.api.dependencies.validate_session_ownership",
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await validate_session(request, current_user=_current_user())
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_threshold_exceeded_returns_429(self):
        request = self._request()
        with (
            patch("app.api.dependencies.validate_session_ownership", new_callable=AsyncMock),
            patch(
                "app.api.dependencies.increment_session_messages",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(message_count=10_000),
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await validate_session(request, current_user=_current_user())
        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    async def test_database_error_returns_500(self):
        request = self._request()
        with patch(
            "app.api.dependencies.validate_session_ownership",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("connection refused"),
        ):
            with pytest.raises(HTTPException) as exc:
                await validate_session(request, current_user=_current_user())
        assert exc.value.status_code == 500
        assert exc.value.detail == "Database operation failed"
