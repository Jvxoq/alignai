from pydantic import BaseModel, Field


class AlignRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    feature_text: str = Field(..., min_length=1, max_length=5000)
