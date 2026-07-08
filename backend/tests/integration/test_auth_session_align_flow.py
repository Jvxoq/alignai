from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.database import UserRecord
from main import app

client = TestClient(app)


class TestAuthSessionAlignHappyPath:
    """Exercises the real seam between layers: a token minted by /auth/signup
    is decoded by the real get_current_user dependency on /sessions and
    /align, rather than each endpoint being tested in isolation against a
    stubbed user. Only the database and LangGraph boundaries are mocked.
    """

    def test_signup_then_create_session_then_align(self):
        user_id = uuid4()
        user_record = UserRecord(
            id=user_id,
            email="flow@example.com",
            hashed_password="irrelevant-hash",
            is_active=True,
        )
        user_record.created_at = datetime.now(timezone.utc)

        with (
            patch(
                "app.services.auth_service.get_user_by_email",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.auth_service.create_user",
                new_callable=AsyncMock,
                return_value=user_record,
            ),
        ):
            signup_response = client.post(
                "/auth/signup",
                json={"email": "flow@example.com", "password": "correct-horse-battery"},
            )
        assert signup_response.status_code == 201
        access_token = signup_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        now = datetime.now(timezone.utc)
        from types import SimpleNamespace

        session_record = SimpleNamespace(
            id=uuid4(),
            user_id=user_id,
            title=None,
            message_count=0,
            last_active_at=now,
            created_at=now,
        )

        with (
            patch(
                "app.api.dependencies.get_user_by_id",
                new_callable=AsyncMock,
                return_value=user_record,
            ),
            patch(
                "app.api.routes.sessions.create_user_session",
                new_callable=AsyncMock,
                return_value=session_record,
            ),
        ):
            session_response = client.post("/sessions", headers=headers)
        assert session_response.status_code == 201
        session_id = session_response.json()["id"]
        assert session_response.json()["message_count"] == 0

        async def fake_stream():
            yield 'event: start\ndata: {"type":"start","response_type":"chat"}\n\n'
            yield 'event: done\ndata: {"type":"done"}\n\n'

        with (
            patch(
                "app.api.dependencies.get_user_by_id",
                new_callable=AsyncMock,
                return_value=user_record,
            ),
            patch(
                "app.api.dependencies.validate_session_ownership",
                new_callable=AsyncMock,
                return_value=session_record,
            ),
            patch(
                "app.api.dependencies.increment_session_messages",
                new_callable=AsyncMock,
                return_value=session_record,
            ),
            patch("app.api.routes.align.stream_align", return_value=fake_stream()),
        ):
            align_response = client.post(
                "/align",
                headers=headers,
                json={"session_id": session_id, "user_message": "Describe my feature"},
            )
        assert align_response.status_code == 200
        assert align_response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert "event: start" in align_response.text
        assert "event: done" in align_response.text

    def test_align_rejected_when_token_missing(self):
        response = client.post(
            "/align",
            json={"session_id": str(uuid4()), "user_message": "Test"},
        )
        assert response.status_code == 401

    def test_align_rejected_with_token_from_different_flow_but_inactive_user(self):
        # A structurally valid token whose user has since been deactivated
        # must still be rejected by the real get_current_user dependency,
        # even though the token itself decodes successfully.
        user_id = uuid4()
        from app.infrastructure.auth import create_access_token

        token = create_access_token(user_id)
        inactive_user = UserRecord(
            id=user_id,
            email="deactivated@example.com",
            hashed_password="irrelevant-hash",
            is_active=False,
        )
        inactive_user.created_at = datetime.now(timezone.utc)

        with patch(
            "app.api.dependencies.get_user_by_id",
            new_callable=AsyncMock,
            return_value=inactive_user,
        ):
            response = client.post(
                "/sessions",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401
