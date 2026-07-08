from pydantic import BaseModel, Field


class RewrittenObjective(BaseModel):
    """Structured output for objective rewriting."""

    objective: str = Field(
        description="The rewritten, more targeted retrieval objective (max 30 words).",
    )
