import asyncio
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_AGENT_HEALTH_PATH = "/ok"


async def _ping_agent_once(client: httpx.AsyncClient, url: str) -> None:
    try:
        response = await client.get(url)
        if response.status_code >= 400:
            logger.warning("Agent keep-alive ping got HTTP %s from %s", response.status_code, url)
        else:
            logger.debug("Agent keep-alive ping OK (%s)", url)
    except httpx.HTTPError as exc:
        # Expected during a real cold start or a transient blip — the retry
        # loop below will simply try again next interval. Never let a failed
        # ping crash the background task or the app.
        logger.warning("Agent keep-alive ping failed: %s", exc)


async def run_keep_alive_loop() -> None:
    """Background task: periodically pings the agent so it never idles long
    enough for the platform to put it to sleep. Runs until cancelled."""
    settings = get_settings()
    if not settings.AGENT_KEEP_ALIVE_ENABLED:
        return

    url = f"{settings.LANGGRAPH_SERVER_URL.rstrip('/')}{_AGENT_HEALTH_PATH}"
    interval = settings.AGENT_KEEP_ALIVE_INTERVAL_SECONDS
    timeout = settings.AGENT_KEEP_ALIVE_TIMEOUT_SECONDS

    logger.info("Starting agent keep-alive loop: %s every %ss", url, interval)

    async with httpx.AsyncClient(timeout=timeout) as client:
        while True:
            await _ping_agent_once(client, url)
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

    logger.info("Agent keep-alive loop stopped")
