from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_health_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_warm_reports_ok_when_both_dependencies_wake():
    with patch("app.api.routes.align.check_database", AsyncMock(return_value=True)), \
            patch("app.api.routes.align.wake_agent", AsyncMock(return_value=True)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/warm")
    assert response.status_code == 200
    assert response.json() == {"backend": "ok", "db": "ok", "agent": "ok"}


@pytest.mark.asyncio
async def test_warm_reports_waking_for_cold_dependencies_without_erroring():
    # A cold/unreachable dependency must never turn the warm-up into a 500 —
    # it's a best-effort nudge, so it degrades to "waking".
    with patch("app.api.routes.align.check_database", AsyncMock(return_value=False)), \
            patch("app.api.routes.align.wake_agent", AsyncMock(return_value=False)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/warm")
    assert response.status_code == 200
    assert response.json() == {"backend": "ok", "db": "waking", "agent": "waking"}
