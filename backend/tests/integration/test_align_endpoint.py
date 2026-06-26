from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, validate_session
from app.models.user import UserResponse
from main import app

client = TestClient(app)


@pytest.fixture
def user() -> UserResponse:
    return UserResponse(
        id=uuid4(),
        email="test@example.com",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def as_authenticated(user):
    # Override authentication so endpoint tests exercise the route logic
    # without a real token or database. Cleared after each test.
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.clear()


def _session_record(message_count: int = 0):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        title=None,
        message_count=message_count,
        last_active_at=now,
        created_at=now,
    )


class TestAlignEndpoint:
    def test_align_without_auth_returns_401(self):
        app.dependency_overrides.clear()
        response = client.post(
            "/align",
            json={"session_id": str(uuid4()), "user_message": "Test message"},
        )
        assert response.status_code == 401

    def test_align_with_malformed_session_id_returns_422(self, as_authenticated):
        # The session_id field is regex-validated on AlignRequest, so a
        # non-UUID value is rejected at the model layer before the handler runs.
        response = client.post(
            "/align",
            json={"session_id": "invalid-uuid", "user_message": "Test"},
        )
        assert response.status_code == 422

    def test_align_with_nonexistent_session_returns_404(self, as_authenticated):
        with patch(
            "app.api.dependencies.validate_session_ownership",
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied",
            ),
        ):
            response = client.post(
                "/align",
                json={"session_id": str(uuid4()), "user_message": "Test"},
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Session not found or access denied"

    def test_align_over_threshold_returns_429(self, as_authenticated):
        with (
            patch("app.api.dependencies.validate_session_ownership", new_callable=AsyncMock),
            patch(
                "app.api.dependencies.increment_session_messages",
                new_callable=AsyncMock,
                return_value=_session_record(message_count=9999),
            ),
        ):
            response = client.post(
                "/align",
                json={"session_id": str(uuid4()), "user_message": "Test"},
            )
        assert response.status_code == 429

    def test_align_with_valid_request_returns_sse_stream(self, as_authenticated):
        async def fake_stream():
            yield 'event: start\ndata: {"type":"start","response_type":"chat"}\n\n'
            yield 'event: done\ndata: {"type":"done"}\n\n'

        # validate_session is exercised in the tests above; here we isolate the
        # streaming response, so we override it to return a valid session id.
        app.dependency_overrides[validate_session] = lambda: str(uuid4())
        with patch("app.api.routes.align.stream_align", return_value=fake_stream()):
            response = client.post(
                "/align",
                json={"session_id": str(uuid4()), "user_message": "Test message"},
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["Cache-Control"] == "no-cache"

    def test_align_streams_all_event_types(self, as_authenticated):
        async def fake_stream():
            yield 'event: start\ndata: {"type":"start","response_type":"report"}\n\n'
            yield 'event: status\ndata: {"type":"status","message":"Retrieving..."}\n\n'
            yield 'event: token\ndata: {"type":"token","data":"Test"}\n\n'
            yield 'event: done\ndata: {"type":"done"}\n\n'

        app.dependency_overrides[validate_session] = lambda: str(uuid4())
        with patch("app.api.routes.align.stream_align", return_value=fake_stream()):
            response = client.post(
                "/align",
                json={"session_id": str(uuid4()), "user_message": "Test"},
            )

        assert response.status_code == 200
        content = response.text
        assert "event: start" in content
        assert "event: status" in content
        assert "event: token" in content
        assert "event: done" in content
