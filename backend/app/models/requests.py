from pydantic import BaseModel, Field


class AlignRequest(BaseModel):
    session_id: str = Field(..., pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    user_message: str = Field(..., min_length=1, max_length=2000)


class UpdateSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)