from typing import Optional

from pydantic import BaseModel, Field


class IntentClassification(BaseModel):
    """Structured output for intent classification."""

    objective: Optional[str] = Field(
        default=None,
        description="Concise retrieval goal (max 30 words) for EU AI Act compliance queries. Null if general conversation.",
    )
    response: Optional[str] = Field(
        default=None,
        description="Formal response for general conversational messages unrelated to the EU AI Act. Null if compliance-related.",
    )
