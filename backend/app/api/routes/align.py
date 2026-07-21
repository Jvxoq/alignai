import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import validate_session
from app.core.limiter import limiter
from app.infrastructure.database import check_database
from app.infrastructure.keep_alive import wake_agent
from app.models.requests import AlignRequest
from app.services.align_service import stream_align

router = APIRouter()


@router.get(
    "/health",
    summary="Health check endpoint",
    response_description="Returns service health status",
)
async def health():
    """
    Health check endpoint for monitoring service availability.

    Returns a simple status object indicating the service is running.

    Kept intentionally shallow (no DB/agent calls) because the platform uses
    this as its health probe — it must stay fast and not fail on a transient
    DB blip. Use /health/warm to wake dependent services.
    """
    return {"status": "ok"}


@router.get(
    "/health/warm",
    summary="Warm up sleeping services",
    response_description="Per-dependency wake status",
)
@limiter.limit("12/minute")
async def warm(request: Request):
    """
    Wake the free-tier dependencies (Postgres + agent) so the first real user
    request isn't blocked by a cold start.

    The frontend calls this on page load. Reaching this route already woke the
    backend; here we wake the DB (a SELECT 1, which also spins up Neon's
    scale-to-zero endpoint) and the agent (a health ping) in parallel. Always
    returns 200 — this is a best-effort nudge, not a strict health gate. A
    dependency reports "waking" when the wake was triggered but hadn't finished
    answering yet.
    """
    db_ok, agent_ok = await asyncio.gather(check_database(), wake_agent())
    return {
        "backend": "ok",
        "db": "ok" if db_ok else "waking",
        "agent": "ok" if agent_ok else "waking",
    }


@router.post(
    "/align",
    summary="Generate EU AI Act compliance report",
    response_description="Server-Sent Events stream of report generation progress",
    status_code=200,
)
@limiter.limit("30/minute")
async def align(
    request: Request,
    body: AlignRequest,
    session_id: str = Depends(validate_session),
):
    """
    Stream an EU AI Act compliance audit report for a given feature description.

    This endpoint uses Server-Sent Events (SSE) to stream the agent's progress in real-time:
    - **start**: Indicates response type (chat/report/failure)
    - **status**: Progress updates during retrieval/rewriting
    - **token**: Incremental content tokens for the generated response
    - **done**: Stream completion signal
    - **error**: Error event with code and message

    **Authentication:** Requires Bearer token in Authorization header

    **Rate Limits:**
    - 30 requests per minute per IP address
    - 50 messages per session (configurable via USER_MESSAGE_THRESHOLD)

    **Request Body:**
    - **session_id**: Valid UUID of user's session
    - **user_message**: Feature description to audit (max 2000 characters)

    **Response Format:**
    - SSE stream with media type `text/event-stream`
    - Events follow format: `event: <type>\\ndata: <json>\\n\\n`

    **Errors:**
    - 401: Invalid or missing authentication
    - 403: Session doesn't belong to authenticated user
    - 404: Session not found
    - 429: Rate limit exceeded or message threshold exceeded for session
    - 503: LangGraph agent unavailable
    - 504: LangGraph agent timeout

    **Example SSE Stream:**
    ```
    event: start
    data: {"type":"start","response_type":"report"}

    event: status
    data: {"type":"status","message":"Retrieving documents..."}

    event: token
    data: {"type":"token","data":"# Compliance Report\\n"}

    event: done
    data: {"type":"done"}
    ```
    """
    body.session_id = session_id
    return StreamingResponse(
        stream_align(body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
