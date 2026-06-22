from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_within_bcrypt_limit(cls, v: str) -> str:
        # bcrypt only hashes the first 72 bytes; reject anything longer so the
        # input is never silently truncated. max_length above bounds characters,
        # but multibyte characters can exceed 72 bytes within 72 characters.
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool
    created_at: datetime


class SessionResponse(BaseModel):
    id: UUID
    title: str | None
    message_count: int
    last_active_at: datetime
    created_at: datetime


class ChatMessage(BaseModel):
    role: str
    content: str


class SessionMessagesResponse(BaseModel):
    messages: list[ChatMessage]


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
