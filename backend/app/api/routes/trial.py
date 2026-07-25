import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import require_unused_trial
from app.core.config import settings
from app.core.limiter import limiter
from app.infrastructure.auth import TRIAL_COOKIE_NAME, create_trial_token
from app.models.requests import AlignRequest, TrialAlignRequest
from app.services.align_service import stream_align

router = APIRouter(prefix="/trial")


@router.post(
    "/align",
    summary="Free trial: generate one EU AI Act compliance report",
    response_description="Server-Sent Events stream of report generation progress",
    status_code=200,
)
@limiter.limit("5/day")
async def trial_align(
    request: Request,
    body: TrialAlignRequest,
    _: None = Depends(require_unused_trial),
):
    """
    Stream a single, unauthenticated trial compliance report.

    Lets a first-time visitor try the product once before signing in. No DB
    session is created; the trial is tracked via a signed cookie set on the
    response, not a database row.

    **Rate Limit:** 5 requests per day per IP address (abuse backstop)

    **Request Body:**
    - **user_message**: Feature description to audit (max 2000 characters)

    **Errors:**
    - 403: Trial already used (cookie present)
    - 429: Rate limit exceeded
    - 503: LangGraph agent unavailable
    - 504: LangGraph agent timeout
    """
    thread_id = str(uuid.uuid4())
    align_request = AlignRequest(session_id=thread_id, user_message=body.user_message)
    response = StreamingResponse(
        stream_align(align_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    is_production = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key=TRIAL_COOKIE_NAME,
        value=create_trial_token(),
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
    )
    return response
