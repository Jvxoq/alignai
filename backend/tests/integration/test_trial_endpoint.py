from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.limiter import limiter
from app.infrastructure.auth import TRIAL_COOKIE_NAME, create_trial_token
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limit():
    # The route is capped at 5/day per IP; without a reset, running this file
    # more than a few times would start failing on the limiter, not the logic
    # under test.
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def clear_client_cookies():
    # TestClient persists Set-Cookie responses across requests on the shared
    # client, so a trial cookie set by one test would otherwise leak into the
    # next and make it look like the trial was already used.
    client.cookies.clear()
    yield
    client.cookies.clear()


def _fake_stream():
    async def gen():
        yield 'event: start\ndata: {"type":"start","response_type":"report"}\n\n'
        yield 'event: done\ndata: {"type":"done"}\n\n'

    return gen()


class TestTrialAlignEndpoint:
    def test_trial_without_cookie_streams_and_sets_cookie(self):
        with patch("app.api.routes.trial.stream_align", return_value=_fake_stream()):
            response = client.post(
                "/trial/align",
                json={"user_message": "Test message"},
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert TRIAL_COOKIE_NAME in response.cookies

    def test_trial_with_valid_used_cookie_returns_403(self):
        token = create_trial_token()
        client.cookies.set(TRIAL_COOKIE_NAME, token)
        with patch("app.api.routes.trial.stream_align", return_value=_fake_stream()):
            response = client.post(
                "/trial/align",
                json={"user_message": "Test message"},
            )

        assert response.status_code == 403
        assert "already used" in response.json()["detail"]

    def test_trial_with_garbage_cookie_still_allows_trial(self):
        # A malformed cookie value must not itself lock the visitor out.
        client.cookies.set(TRIAL_COOKIE_NAME, "not-a-jwt")
        with patch("app.api.routes.trial.stream_align", return_value=_fake_stream()):
            response = client.post(
                "/trial/align",
                json={"user_message": "Test message"},
            )

        assert response.status_code == 200

    def test_trial_with_empty_message_returns_422(self):
        response = client.post("/trial/align", json={"user_message": ""})
        assert response.status_code == 422

    def test_trial_with_oversized_message_returns_422(self):
        response = client.post(
            "/trial/align",
            json={"user_message": "x" * 2001},
        )
        assert response.status_code == 422

    def test_trial_does_not_accept_session_id(self):
        # The trial request model has no session_id field; a real session
        # must never be created or reused for an unauthenticated trial.
        with patch("app.api.routes.trial.stream_align", return_value=_fake_stream()):
            response = client.post(
                "/trial/align",
                json={"user_message": "Test message", "session_id": "should-be-ignored"},
            )

        assert response.status_code == 200
