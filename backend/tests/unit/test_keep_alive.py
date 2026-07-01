import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.infrastructure.keep_alive import _ping_agent_once, run_keep_alive_loop


@pytest.mark.asyncio
async def test_ping_agent_once_swallows_http_errors():
    client = AsyncMock()
    client.get.side_effect = httpx.ConnectError("agent asleep")

    # Must not raise — a failed ping should never take down the loop.
    await _ping_agent_once(client, "http://agent/ok")

    client.get.assert_awaited_once_with("http://agent/ok")


@pytest.mark.asyncio
async def test_ping_agent_once_warns_on_non_2xx_without_raising():
    client = AsyncMock()
    client.get.return_value = MagicMock(status_code=503)

    await _ping_agent_once(client, "http://agent/ok")

    client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_keep_alive_loop_noop_when_disabled():
    settings = MagicMock(AGENT_KEEP_ALIVE_ENABLED=False)
    with patch("app.infrastructure.keep_alive.get_settings", return_value=settings), \
            patch("app.infrastructure.keep_alive.httpx.AsyncClient") as mock_client_cls:
        await run_keep_alive_loop()

    mock_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_run_keep_alive_loop_pings_agent_ok_endpoint_and_sleeps_between_pings():
    settings = MagicMock(
        AGENT_KEEP_ALIVE_ENABLED=True,
        LANGGRAPH_SERVER_URL="http://agent:8123",
        AGENT_KEEP_ALIVE_INTERVAL_SECONDS=600,
        AGENT_KEEP_ALIVE_TIMEOUT_SECONDS=30,
    )

    sleep_calls = []

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 2:
            raise asyncio.CancelledError()

    with patch("app.infrastructure.keep_alive.get_settings", return_value=settings), \
            patch("app.infrastructure.keep_alive.asyncio.sleep", side_effect=fake_sleep):
        mock_ping = AsyncMock()
        with patch("app.infrastructure.keep_alive._ping_agent_once", mock_ping):
            await run_keep_alive_loop()

    assert sleep_calls == [600, 600]
    assert mock_ping.await_count == 2
    called_url = mock_ping.await_args_list[0].args[1]
    assert called_url == "http://agent:8123/ok"


@pytest.mark.asyncio
async def test_run_keep_alive_loop_strips_trailing_slash_from_base_url():
    settings = MagicMock(
        AGENT_KEEP_ALIVE_ENABLED=True,
        LANGGRAPH_SERVER_URL="http://agent:8123/",
        AGENT_KEEP_ALIVE_INTERVAL_SECONDS=600,
        AGENT_KEEP_ALIVE_TIMEOUT_SECONDS=30,
    )

    async def cancel_after_first_sleep(seconds):
        raise asyncio.CancelledError()

    with patch("app.infrastructure.keep_alive.get_settings", return_value=settings), \
            patch("app.infrastructure.keep_alive.asyncio.sleep", side_effect=cancel_after_first_sleep):
        mock_ping = AsyncMock()
        with patch("app.infrastructure.keep_alive._ping_agent_once", mock_ping):
            await run_keep_alive_loop()

    called_url = mock_ping.await_args_list[0].args[1]
    assert called_url == "http://agent:8123/ok"
