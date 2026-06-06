import asyncio
import logging
from collections.abc import AsyncGenerator

from app.models.requests import AlignRequest
from app.models.responses import DoneEvent, ErrorEvent, SSEEvent, StatusEvent, TokenEvent

logger = logging.getLogger(__name__)

MOCK_REPORT = (
    "## Alignment Report\n\n"
    "Your feature description aligns well with standard product practices. "
    "Consider adding acceptance criteria and edge-case handling."
)


def _format_sse(event: SSEEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


async def stream_align(request: AlignRequest) -> AsyncGenerator[str, None]:
    """Stream alignment results as SSE events.

    Skeleton implementation yields mock events. Replace with
    astream_events from RemoteGraph + retry logic for production.
    """
    try:
        yield _format_sse(StatusEvent(message="Analyzing feature description..."))
        await asyncio.sleep(0.1)

        tokens = MOCK_REPORT.split()
        for token in tokens:
            yield _format_sse(TokenEvent(content=token + " "))
            await asyncio.sleep(0.02)

        yield _format_sse(DoneEvent(report=MOCK_REPORT))
    except Exception as exc:
        logger.exception("Align stream failed")
        yield _format_sse(ErrorEvent(message=str(exc)))
