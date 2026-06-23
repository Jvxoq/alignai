from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
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


@pytest.fixture(autouse=True)
def _auth(user):
    app.dependency_overrides[get_current_user] = lambda: user
    yield
    app.dependency_overrides.clear()


def _session_record(title=None, message_count: int = 0):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        title=title,
        message_count=message_count,
        last_active_at=now,
        created_at=now,
    )


class TestCreateSession:
    def test_returns_201_with_serialized_record(self):
        record = _session_record()
        with patch(
            "app.api.routes.sessions.create_user_session",
            new_callable=AsyncMock,
            return_value=record,
        ):
            response = client.post("/sessions")
        assert response.status_code == 201
        body = response.json()
        assert body["id"] == str(record.id)
        assert body["title"] is None
        assert body["message_count"] == 0


class TestListSessions:
    def test_returns_paginated_payload_with_has_more(self):
        records = [_session_record(), _session_record()]
        with patch(
            "app.api.routes.sessions.list_user_sessions",
            new_callable=AsyncMock,
            return_value=(records, 5),
        ):
            response = client.get("/sessions", params={"limit": 2, "offset": 0})
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 5
        assert body["limit"] == 2
        assert body["offset"] == 0
        assert len(body["sessions"]) == 2
        assert body["has_more"] is True  # 0 + 2 < 5

    def test_has_more_false_on_last_page(self):
        records = [_session_record()]
        with patch(
            "app.api.routes.sessions.list_user_sessions",
            new_callable=AsyncMock,
            return_value=(records, 1),
        ):
            response = client.get("/sessions", params={"limit": 50, "offset": 0})
        assert response.status_code == 200
        assert response.json()["has_more"] is False

    def test_rejects_out_of_range_limit(self):
        response = client.get("/sessions", params={"limit": 0})
        assert response.status_code == 422


class TestSessionMessages:
    def test_returns_messages(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        with patch(
            "app.api.routes.sessions.get_session_messages",
            new_callable=AsyncMock,
            return_value=messages,
        ):
            response = client.get(f"/sessions/{uuid4()}/messages")
        assert response.status_code == 200
        assert response.json()["messages"] == messages


class TestUpdateSession:
    def test_returns_updated_title(self):
        record = _session_record(title="New Title")
        with patch(
            "app.api.routes.sessions.update_session_title",
            new_callable=AsyncMock,
            return_value=record,
        ):
            response = client.patch(f"/sessions/{uuid4()}", json={"title": "New Title"})
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"

    def test_rejects_empty_title(self):
        response = client.patch(f"/sessions/{uuid4()}", json={"title": ""})
        assert response.status_code == 422


class TestDeleteSession:
    def test_returns_204_when_deleted(self):
        with patch(
            "app.api.routes.sessions.delete_user_session",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = client.delete(f"/sessions/{uuid4()}")
        assert response.status_code == 204

    def test_returns_404_when_not_owned_or_missing(self):
        with patch(
            "app.api.routes.sessions.delete_user_session",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = client.delete(f"/sessions/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Session not found or access denied"


class TestDeleteAccount:
    def test_returns_204(self):
        with patch(
            "app.api.routes.users.delete_user_account",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = client.delete("/users/me")
        assert response.status_code == 204


class TestSessionsRequireAuth:
    def test_unauthenticated_create_returns_401(self):
        app.dependency_overrides.clear()
        response = client.post("/sessions")
        assert response.status_code == 401
