from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user
from app.models.user import UserResponse
from app.services.auth_service import delete_user_account

router = APIRouter(prefix="/users", tags=["users"])


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete the current user account",
    response_description="No content on successful deletion",
)
async def delete_account_route(current_user: UserResponse = Depends(get_current_user)) -> None:
    """
    Permanently delete the authenticated user's account.

    Sessions owned by the user are removed via the database cascade. This action
    is permanent and cannot be undone.

    **Authentication:** Requires Bearer token in Authorization header

    **Errors:**
    - 401: Invalid or missing authentication
    """
    await delete_user_account(current_user.id)