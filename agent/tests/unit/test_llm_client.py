from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from groq import APIConnectionError
from pydantic import BaseModel

from app.infrastructure import llm_client
from app.infrastructure.llm_client import call_llm, call_llm_structured


class _Schema(BaseModel):
    objective: str | None = None


def _settings(**overrides):
    base = dict(
        GROQ_API_KEY="test-key",
        LLM_MODEL="llama-3.3-70b-versatile",
        LLM_TEMPERATURE=0.1,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _fake_chat_groq(response_content="ok", structured_result=None):
    instances = []

    def make(**kwargs):
        instance = SimpleNamespace(**kwargs)
        instance.ainvoke = AsyncMock(return_value=SimpleNamespace(content=response_content))
        instance.with_structured_output = lambda schema: SimpleNamespace(
            ainvoke=AsyncMock(return_value=structured_result)
        )
        instances.append(instance)
        return instance

    return make, instances


@pytest.mark.asyncio
async def test_call_llm_uses_default_model_when_none_given():
    make, instances = _fake_chat_groq()
    with patch.object(llm_client, "get_settings", return_value=_settings()):
        with patch.object(llm_client, "ChatGroq", side_effect=make):
            await call_llm("prompt")
    assert instances[0].model == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_call_llm_uses_explicit_model_override():
    make, instances = _fake_chat_groq()
    with patch.object(llm_client, "get_settings", return_value=_settings()):
        with patch.object(llm_client, "ChatGroq", side_effect=make):
            await call_llm("prompt", model="llama-3.1-8b-instant")
    assert instances[0].model == "llama-3.1-8b-instant"


@pytest.mark.asyncio
async def test_call_llm_structured_uses_explicit_model_override():
    make, instances = _fake_chat_groq(structured_result=_Schema(objective="x"))
    with patch.object(llm_client, "get_settings", return_value=_settings()):
        with patch.object(llm_client, "ChatGroq", side_effect=make):
            result = await call_llm_structured("prompt", _Schema, model="llama-guard-4-12b")
    assert instances[0].model == "llama-guard-4-12b"
    assert result.objective == "x"


@pytest.mark.asyncio
async def test_call_llm_structured_uses_default_model_when_none_given():
    make, instances = _fake_chat_groq(structured_result=_Schema(objective="x"))
    with patch.object(llm_client, "get_settings", return_value=_settings()):
        with patch.object(llm_client, "ChatGroq", side_effect=make):
            await call_llm_structured("prompt", _Schema)
    assert instances[0].model == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_call_llm_raises_without_api_key():
    with patch.object(llm_client, "get_settings", return_value=_settings(GROQ_API_KEY="")):
        with pytest.raises(RuntimeError, match="not configured"):
            await call_llm("prompt")


@pytest.mark.asyncio
async def test_call_llm_retries_on_groq_connection_error():
    request = httpx.Request("POST", "https://api.groq.com")
    call_count = 0

    def make(**kwargs):
        nonlocal call_count
        instance = SimpleNamespace(**kwargs)

        async def ainvoke(_messages):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise APIConnectionError(request=request)
            return SimpleNamespace(content="ok")

        instance.ainvoke = ainvoke
        return instance

    # LLM_MAX_RETRIES (default 3) is read at import time into the module-level
    # `_settings` the @retry decorator is built from, not per-call -- the real
    # default already covers this test's 2 attempts.
    with patch.object(llm_client, "get_settings", return_value=_settings()):
        with patch.object(llm_client, "ChatGroq", side_effect=make):
            result = await call_llm("prompt")

    assert result == "ok"
    assert call_count == 2
