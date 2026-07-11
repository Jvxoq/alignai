import logging
from typing import TypeVar, cast

from groq import APIConnectionError, InternalServerError, RateLimitError
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel, SecretStr
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings, settings as _settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# groq.APIConnectionError/APITimeoutError (real network failures talking to
# Groq) don't inherit from the builtin ConnectionError/TimeoutError, so they
# need to be listed explicitly or they silently skip the retry entirely.
_RETRYABLE = (RateLimitError, InternalServerError, APIConnectionError, ConnectionError, TimeoutError)


@retry(
    stop=stop_after_attempt(_settings.LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
async def call_llm(prompt: str, model: str | None = None) -> str:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")
    llm = ChatGroq(  # type: ignore[call-arg]  # `model` is ChatGroq's alias for `model_name`
        api_key=SecretStr(settings.GROQ_API_KEY),
        model=model or settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=2048,
    )
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return str(response.content or "")


@retry(
    stop=stop_after_attempt(_settings.LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_RETRYABLE),
    reraise=True,
)
async def call_llm_structured(prompt: str, schema: type[T], model: str | None = None) -> T:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")
    llm = ChatGroq(  # type: ignore[call-arg]  # `model` is ChatGroq's alias for `model_name`
        api_key=SecretStr(settings.GROQ_API_KEY),
        model=model or settings.LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=2048,
    )
    structured = llm.with_structured_output(schema)
    result = await structured.ainvoke([HumanMessage(content=prompt)])
    return cast(T, result)
