import logging
from typing import TypeVar

from groq import InternalServerError, RateLimitError
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_RETRYABLE = (RateLimitError, InternalServerError, ConnectionError, TimeoutError)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
async def call_llm(prompt: str) -> str:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")
    model = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=2048,
        streaming=True,
    )
    response = await model.ainvoke([HumanMessage(content=prompt)])
    return response.content or ""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
async def call_llm_structured(prompt: str, schema: type[T]) -> T:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")
    model = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=2048,
        streaming=True,
    )
    structured = model.with_structured_output(schema)
    result = await structured.ainvoke([HumanMessage(content=prompt)])
    return result
