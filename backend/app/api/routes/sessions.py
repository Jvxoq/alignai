from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user
from app.models.requests import UpdateSessionRequest
from app.models.user import SessionListResponse, SessionResponse, SessionMessagesResponse, UserResponse
from app.services.session_service import (
    create_user_session,
    delete_user_session,
    get_session_messages,
    list_user_sessions,
    update_session_title,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=201,
    summary="Create a new session",
    response_description="Created session details",
)
async def create_session_route(
    current_user: UserResponse = Depends(get_current_user),
) -> SessionResponse:
    """
    Create a new conversation session for the authenticated user.

    Sessions track conversation history and message counts for rate limiting.

    **Authentication:** Requires Bearer token in Authorization header

    **Returns:**
    - **id**: Session UUID
    - **title**: Session title (null initially)
    - **message_count**: Number of messages (starts at 0)
    - **last_active_at**: Last activity timestamp
    - **created_at**: Session creation timestamp

    **Errors:**
    - 401: Invalid or missing authentication
    """
    record = await create_user_session(current_user.id)
    return SessionResponse.model_validate(record, from_attributes=True)


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List user sessions",
    response_description="Paginated list of user's sessions ordered by last activity",
)
async def list_sessions_route(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    current_user: UserResponse = Depends(get_current_user),
) -> SessionListResponse:
    """
    Retrieve sessions for the authenticated user with pagination support.

    Sessions are returned in descending order by last_active_at (most recent first).

    **Authentication:** Requires Bearer token in Authorization header

    **Query Parameters:**
    - **limit**: Maximum sessions to return (1-100, default 50)
    - **offset**: Number of sessions to skip for pagination (default 0)

    **Returns:**
    - **sessions**: Array of session objects
    - **total**: Total number of sessions for user
    - **limit**: Applied limit value
    - **offset**: Applied offset value
    - **has_more**: Whether more sessions are available

    **Errors:**
    - 401: Invalid or missing authentication
    - 422: Invalid pagination parameters
    """
    records, total = await list_user_sessions(current_user.id, limit, offset)
    sessions = [SessionResponse.model_validate(r, from_attributes=True) for r in records]
    return SessionListResponse(
        sessions=sessions,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total,
    )


@router.get(
    "/{session_id}/messages",
    response_model=SessionMessagesResponse,
    summary="Get session conversation history",
    response_description="Array of messages in chronological order",
)
async def get_session_messages_route(
    session_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> SessionMessagesResponse:
    """
    Retrieve the conversation history for a specific session.

    **Authentication:** Requires Bearer token in Authorization header

    **Path Parameters:**
    - **session_id**: UUID of the session

    **Returns:**
    - **messages**: Array of message objects with role and content

    **Errors:**
    - 401: Invalid or missing authentication
    - 404: Session not found or access denied
    """
    messages = await get_session_messages(session_id, current_user.id)
    return SessionMessagesResponse(messages=messages)


@router.delete(
    "/{session_id}",
    status_code=204,
    summary="Delete a session",
    response_description="No content on successful deletion",
)
async def delete_session_route(
    session_id: UUID,
    current_user: UserResponse = Depends(get_current_user),
) -> None:
    """
    Delete a session and its associated conversation history.

    This action is permanent and cannot be undone. The LangGraph thread is also deleted.

    **Authentication:** Requires Bearer token in Authorization header

    **Path Parameters:**
    - **session_id**: UUID of the session to delete

    **Errors:**
    - 401: Invalid or missing authentication
    - 404: Session not found or access denied
    """
    deleted = await delete_user_session(session_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or access denied",
        )


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Update session title",
    response_description="Updated session details",
)
async def update_session_route(
    session_id: UUID,
    request: UpdateSessionRequest,
    current_user: UserResponse = Depends(get_current_user),
) -> SessionResponse:
    """
    Update the title of an existing session.

    **Authentication:** Requires Bearer token in Authorization header

    **Path Parameters:**
    - **session_id**: UUID of the session to update

    **Request Body:**
    - **title**: New session title (max 200 characters)

    **Returns:**
    - Updated session object with new title

    **Errors:**
    - 401: Invalid or missing authentication
    - 404: Session not found or access denied
    - 422: Invalid title format
    """
    record = await update_session_title(session_id, current_user.id, request.title)
    return SessionResponse.model_validate(record, from_attributes=True)
