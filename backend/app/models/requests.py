from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings


class AlignRequest(BaseModel):
    session_id: str = Field(..., pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    user_message: str = Field(..., min_length=1)

    @field_validator("user_message")
    @classmethod
    def validate_message_length(cls, v: str) -> str:
        max_length = get_settings().MAX_MESSAGE_LENGTH
        if len(v) > max_length:
            raise ValueError(f"user_message exceeds maximum length of {max_length}")
        return v


class UpdateSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)