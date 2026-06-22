from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_current_user
from app.core.limiter import limiter
from app.models.user import RefreshRequest, TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import login, refresh, signup

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=201,
    summary="Register a new user account",
    response_description="JWT access and refresh tokens",
)
@limiter.limit("3/minute")
async def signup_route(request: Request, body: UserCreate) -> TokenResponse:
    """
    Create a new user account with email and password.

    **Rate Limit:** 3 requests per minute per IP address

    **Request Body:**
    - **email**: Valid email address (must be unique)
    - **password**: User password (will be hashed)

    **Returns:**
    - **access_token**: JWT token for API authentication (expires in 30 minutes)
    - **refresh_token**: JWT token for refreshing access (expires in 7 days)

    **Errors:**
    - 409: Email already registered
    - 422: Invalid email format or missing fields
    - 429: Too many signup attempts
    """
    return await signup(body.email, body.password)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and receive tokens",
    response_description="JWT access and refresh tokens",
)
@limiter.limit("5/minute")
async def login_route(request: Request, body: UserLogin) -> TokenResponse:
    """
    Authenticate user with email and password credentials.

    **Rate Limit:** 5 requests per minute per IP address

    **Request Body:**
    - **email**: Registered email address
    - **password**: User password

    **Returns:**
    - **access_token**: JWT token for API authentication (expires in 30 minutes)
    - **refresh_token**: JWT token for refreshing access (expires in 7 days)

    **Errors:**
    - 401: Invalid email or password
    - 403: Account is deactivated
    - 422: Invalid request format
    - 429: Too many login attempts
    """
    return await login(body.email, body.password)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    response_description="New JWT access and refresh tokens",
)
@limiter.limit("10/minute")
async def refresh_route(request: Request, body: RefreshRequest) -> TokenResponse:
    """
    Obtain new access and refresh tokens using a valid refresh token.

    **Rate Limit:** 10 requests per minute per IP address

    **Request Body:**
    - **refresh_token**: Valid JWT refresh token

    **Returns:**
    - **access_token**: New JWT access token (expires in 30 minutes)
    - **refresh_token**: New JWT refresh token (expires in 7 days)

    **Errors:**
    - 401: Invalid, expired, or wrong token type
    - 401: User not found or inactive
    - 422: Missing refresh token
    - 429: Too many refresh attempts
    """
    return await refresh(body.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user information",
    response_description="Current authenticated user details",
)
async def me_route(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """
    Retrieve the currently authenticated user's profile information.

    **Authentication:** Requires Bearer token in Authorization header

    **Returns:**
    - **id**: User UUID
    - **email**: User email address
    - **is_active**: Account active status
    - **created_at**: Account creation timestamp

    **Errors:**
    - 401: Invalid or missing authentication token
    """
    return current_user
