from fastapi import HTTPException, status

from app.models.requests import AlignRequest
from app.services.session_service import check_message_threshold, create_or_update_session


async def validate_session(request: AlignRequest) -> str:
    resolved = await create_or_update_session(request.session_id)
    within_threshold = await check_message_threshold(resolved)
    if not within_threshold:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Message threshold exceeded for this session",
        )
    return resolved
