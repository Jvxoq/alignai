from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import validate_session
from app.models.requests import AlignRequest
from app.services.align_service import stream_align

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/align")
async def align(
    request: AlignRequest,
    session_id: str = Depends(validate_session),
):
    request.session_id = session_id
    return StreamingResponse(
        stream_align(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
