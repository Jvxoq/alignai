from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from langchain_core.messages import AIMessage

from app.models.responses import DoneEvent, ErrorEvent, StartEvent, StatusEvent, TokenEvent
from app.services.align_service import (
    _extract_message_text,
    _format_sse,
    _stream_from_langgraph,
    stream_align,
)


def _event(kind: str, name: str, node: str | None = None, data: dict | None = None) -> dict:
    """Build a fake langgraph event. `node` defaults to `name`, i.e. a true node
    boundary (langgraph_node == name). Pass a different `node` to simulate an
    event from a runnable nested inside that node (LLM call, parser, conditional
    edge) — those share the node's langgraph_node but have their own `name`."""
    event: dict = {
        "event": kind,
        "name": name,
        "metadata": {"langgraph_node": node if node is not None else name},
    }
    if data is not None:
        event["data"] = data
    return event


class TestFormatSSE:
    def test_formats_start_event(self):
        event = StartEvent(response_type="chat")
        result = _format_sse(event)
        assert result.startswith("event: start\n")
        assert "data: " in result
        assert '"type":"start"' in result
        assert '"response_type":"chat"' in result
        assert result.endswith("\n\n")

    def test_formats_status_event(self):
        event = StatusEvent(message="Processing...")
        result = _format_sse(event)
        assert "event: status\n" in result
        assert '"message":"Processing..."' in result

    def test_formats_token_event(self):
        event = TokenEvent(data="Hello")
        result = _format_sse(event)
        assert "event: token\n" in result
        assert '"data":"Hello"' in result

    def test_formats_done_event(self):
        event = DoneEvent()
        result = _format_sse(event)
        assert "event: done\n" in result

    def test_formats_error_event(self):
        event = ErrorEvent(code=500, message="Server error")
        result = _format_sse(event)
        assert "event: error\n" in result
        assert '"code":500' in result
        assert '"message":"Server error"' in result


class TestExtractMessageText:
    def test_extracts_from_string_output(self):
        data = {"output": "Simple text response"}
        result = _extract_message_text(data)
        assert result == "Simple text response"

    def test_extracts_from_aimessage_object(self):
        msg = AIMessage(content="AI response")
        data = {"output": {"messages": [msg]}}
        result = _extract_message_text(data)
        assert result == "AI response"

    def test_extracts_from_dict_message(self):
        data = {"output": {"messages": [{"content": "Dict response"}]}}
        result = _extract_message_text(data)
        assert result == "Dict response"

    def test_returns_empty_for_no_output(self):
        data = {}
        result = _extract_message_text(data)
        assert result == ""

    def test_returns_empty_for_no_messages(self):
        data = {"output": {"messages": []}}
        result = _extract_message_text(data)
        assert result == ""

    def test_returns_empty_for_invalid_type(self):
        data = {"output": 123}
        result = _extract_message_text(data)
        assert result == ""


class TestStreamAlign:
    @pytest.mark.asyncio
    async def test_emits_chat_start_when_intent_answers_directly(self):
        """The graph always starts at "intent", so its response_type can't be
        known from on_chain_start alone — it depends on whether intent sets
        an objective (continues to retrieve/generate) or answers directly
        (objective=None, terminal). The "chat" start is only emitted once
        intent's own on_chain_end confirms there's no objective."""
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_start = MagicMock()
        mock_start.data = [_event("on_chain_start", "intent")]

        mock_end = MagicMock()
        mock_end.data = [_event(
            "on_chain_end", "intent",
            data={"output": {"objective": None, "messages": [{"content": "Hi there."}]}},
        )]

        async def mock_stream():
            yield mock_start
            yield mock_end

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            start_events = [e for e in events if "event: start" in e]
            token_events = [e for e in events if "event: token" in e]
            assert len(start_events) == 1
            assert '"response_type":"chat"' in start_events[0]
            assert len(token_events) == 1
            assert '"data":"Hi there."' in token_events[0]

    @pytest.mark.asyncio
    async def test_intent_with_objective_emits_no_start(self):
        """When intent sets an objective, the run continues to retrieve —
        no start event should fire yet (it's deferred to generate/fallback)."""
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_start = MagicMock()
        mock_start.data = [_event("on_chain_start", "intent")]

        mock_end = MagicMock()
        mock_end.data = [_event(
            "on_chain_end", "intent",
            data={"output": {"objective": "EU AI Act Article 9", "messages": []}},
        )]

        async def mock_stream():
            yield mock_start
            yield mock_end

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            start_events = [e for e in events if "event: start" in e]
            assert len(start_events) == 0

    @pytest.mark.asyncio
    async def test_emits_status_event_for_retrieve_node(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_chunk = MagicMock()
        mock_chunk.data = [_event("on_chain_start", "retrieve")]

        async def mock_stream():
            yield mock_chunk

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            status_events = [e for e in events if "event: status" in e]
            assert len(status_events) == 1
            assert "Retrieving documents..." in status_events[0]

    @pytest.mark.asyncio
    async def test_emits_token_events_during_streaming(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_start = MagicMock()
        mock_start.data = [_event("on_chain_start", "generate")]

        mock_token1 = MagicMock()
        mock_token1.data = [_event(
            "on_chat_model_stream", "ChatGroq", node="generate",
            data={"chunk": {"content": "Hello"}},
        )]

        mock_token2 = MagicMock()
        mock_token2.data = [_event(
            "on_chat_model_stream", "ChatGroq", node="generate",
            data={"chunk": {"content": " world"}},
        )]

        async def mock_stream():
            yield mock_start
            yield mock_token1
            yield mock_token2

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            token_events = [e for e in events if "event: token" in e]
            assert len(token_events) == 2
            assert '"data":"Hello"' in token_events[0]
            assert '"data":" world"' in token_events[1]

    @pytest.mark.asyncio
    async def test_emits_done_event_at_end(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        async def mock_stream():
            mock_chunk = MagicMock()
            mock_chunk.data = None
            yield mock_chunk

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            done_events = [e for e in events if "event: done" in e]
            assert len(done_events) == 1

    @pytest.mark.asyncio
    async def test_handles_connection_error(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.side_effect = ConnectionError("Network error")

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            error_events = [e for e in events if "event: error" in e]
            assert len(error_events) == 1
            assert '"code":503' in error_events[0]
            assert "unavailable" in error_events[0]

    @pytest.mark.asyncio
    async def test_handles_timeout_error(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.side_effect = TimeoutError("Timeout")

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            error_events = [e for e in events if "event: error" in e]
            assert len(error_events) == 1
            assert '"code":504' in error_events[0]
            assert "timeout" in error_events[0]

    @pytest.mark.asyncio
    async def test_handles_generic_exception(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.side_effect = Exception("Unexpected error")

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            error_events = [e for e in events if "event: error" in e]
            assert len(error_events) == 1
            assert '"code":500' in error_events[0]

    @pytest.mark.asyncio
    async def test_handles_os_error(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.side_effect = OSError("Socket closed")

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            error_events = [e for e in events if "event: error" in e]
            assert len(error_events) == 1
            assert '"code":503' in error_events[0]

    @pytest.mark.asyncio
    async def test_handles_httpx_connect_error(self):
        """DNS/connect failures during an agent cold start surface as httpx
        errors, not stdlib ConnectionError — must still map to a 503."""
        mock_request = MagicMock(session_id="test-session", user_message="test")

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.side_effect = httpx.ConnectError("Name or service not known")

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            error_events = [e for e in events if "event: error" in e]
            assert len(error_events) == 1
            assert '"code":503' in error_events[0]
            assert "unavailable" in error_events[0]

    @pytest.mark.asyncio
    async def test_handles_httpx_timeout_error(self):
        """A slow cold-start wake-up can exceed the connect/read timeout as an
        httpx.TimeoutException, which isn't a stdlib TimeoutError — must still
        map to a 504."""
        mock_request = MagicMock(session_id="test-session", user_message="test")

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.side_effect = httpx.ConnectTimeout("Connect timed out")

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            error_events = [e for e in events if "event: error" in e]
            assert len(error_events) == 1
            assert '"code":504' in error_events[0]
            assert "timeout" in error_events[0]

    @pytest.mark.asyncio
    async def test_handles_exception_with_server_status_code(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        server_error = Exception("Bad gateway")
        server_error.status_code = 502

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.side_effect = server_error

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            error_events = [e for e in events if "event: error" in e]
            assert len(error_events) == 1
            assert '"code":503' in error_events[0]
            assert "unavailable" in error_events[0]

    @pytest.mark.asyncio
    async def test_emits_start_event_once_for_duplicate_node_starts(self):
        """emitted_start guard should prevent a second start event in the same run,
        e.g. if the SDK ever redelivers a node's on_chain_start."""
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_chunk1 = MagicMock()
        mock_chunk1.data = [_event("on_chain_start", "generate")]
        mock_chunk2 = MagicMock()
        mock_chunk2.data = [_event("on_chain_start", "generate")]

        async def mock_stream():
            yield mock_chunk1
            yield mock_chunk2

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            start_events = [e for e in events if "event: start" in e]
            assert len(start_events) == 1
            assert '"response_type":"report"' in start_events[0]

    @pytest.mark.asyncio
    async def test_emits_start_event_for_generate_node_as_report(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_chunk = MagicMock()
        mock_chunk.data = [_event("on_chain_start", "generate")]

        async def mock_stream():
            yield mock_chunk

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            start_events = [e for e in events if "event: start" in e]
            assert len(start_events) == 1
            assert '"response_type":"report"' in start_events[0]

    @pytest.mark.asyncio
    async def test_emits_start_event_for_fallback_node_as_failure(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_chunk = MagicMock()
        mock_chunk.data = [_event("on_chain_start", "fallback")]

        async def mock_stream():
            yield mock_chunk

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            start_events = [e for e in events if "event: start" in e]
            assert len(start_events) == 1
            assert '"response_type":"failure"' in start_events[0]

    @pytest.mark.asyncio
    async def test_emits_status_event_for_rewrite_objective_node(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_chunk = MagicMock()
        mock_chunk.data = [_event("on_chain_start", "rewrite_objective")]

        async def mock_stream():
            yield mock_chunk

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            status_events = [e for e in events if "event: status" in e]
            assert len(status_events) == 1
            assert "Refining search objective..." in status_events[0]

    @pytest.mark.asyncio
    async def test_extracts_token_from_chunk_object_with_content_attribute(self):
        """on_chat_model_stream chunk may be an object (e.g. AIMessageChunk) rather than a dict."""
        mock_request = MagicMock(session_id="test-session", user_message="test")

        chunk_obj = MagicMock()
        chunk_obj.content = "streamed text"

        mock_start = MagicMock()
        mock_start.data = [_event("on_chain_start", "generate")]

        mock_token = MagicMock()
        mock_token.data = [_event(
            "on_chat_model_stream", "ChatGroq", node="generate",
            data={"chunk": chunk_obj},
        )]

        async def mock_stream():
            yield mock_start
            yield mock_token

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            token_events = [e for e in events if "event: token" in e]
            assert len(token_events) == 1
            assert '"data":"streamed text"' in token_events[0]

    @pytest.mark.asyncio
    async def test_emits_fallback_text_on_chain_end_when_no_tokens_streamed(self):
        """fallback/intent nodes don't stream tokens — on_chain_end must backfill
        a token event from the final output so the client still gets a response."""
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_start = MagicMock()
        mock_start.data = [_event("on_chain_start", "fallback")]

        mock_end = MagicMock()
        mock_end.data = [_event(
            "on_chain_end", "fallback",
            data={"output": {"messages": [{"content": "I can't help with that."}]}},
        )]

        async def mock_stream():
            yield mock_start
            yield mock_end

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            token_events = [e for e in events if "event: token" in e]
            assert len(token_events) == 1
            assert '"data":"I can\'t help with that."' in token_events[0]

    @pytest.mark.asyncio
    async def test_does_not_duplicate_token_on_chain_end_when_already_streamed(self):
        """If tokens were already streamed for this node, on_chain_end must not
        backfill a duplicate token event."""
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_start = MagicMock()
        mock_start.data = [_event("on_chain_start", "generate")]

        mock_token = MagicMock()
        mock_token.data = [_event(
            "on_chat_model_stream", "ChatGroq", node="generate",
            data={"chunk": {"content": "Hello"}},
        )]

        mock_end = MagicMock()
        mock_end.data = [_event(
            "on_chain_end", "generate",
            data={"output": {"messages": [{"content": "Hello"}]}},
        )]

        async def mock_stream():
            yield mock_start
            yield mock_token
            yield mock_end

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            token_events = [e for e in events if "event: token" in e]
            assert len(token_events) == 1

    @pytest.mark.asyncio
    async def test_does_not_emit_token_on_chain_end_when_extracted_text_empty(self):
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_start = MagicMock()
        mock_start.data = [_event("on_chain_start", "intent")]

        mock_end = MagicMock()
        mock_end.data = [_event(
            "on_chain_end", "intent",
            data={"output": {"messages": []}},
        )]

        async def mock_stream():
            yield mock_start
            yield mock_end

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            token_events = [e for e in events if "event: token" in e]
            assert len(token_events) == 0

    @pytest.mark.asyncio
    async def test_handles_chunk_data_as_single_dict_not_list(self):
        """chunk.data is normalized to a list even when the SDK yields a bare dict."""
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_chunk = MagicMock()
        mock_chunk.data = _event("on_chain_start", "generate")

        async def mock_stream():
            yield mock_chunk

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            start_events = [e for e in events if "event: start" in e]
            assert len(start_events) == 1

    @pytest.mark.asyncio
    async def test_nested_runnable_events_do_not_suppress_fallback_token(self):
        """Regression test for a real bug: intent_node's internal LLM call
        (call_llm_structured) is a LangChain Runnable, so it emits its own
        on_chain_start/on_chain_end ("RunnableSequence") nested inside the
        "intent" node, sharing langgraph_node="intent" but with a different
        `name`. The conditional edge function (e.g. should_retrieve) does the
        same. Naively tracking current_node from on_chain_start's bare `name`
        treats these nested pairs as node boundaries and resets tracking state
        before intent's own on_chain_end fires — silently dropping the
        fallback message. This reproduces the exact event sequence captured
        from a live langgraph dev server for a general (non-compliance) query.
        """
        mock_request = MagicMock(session_id="test-session", user_message="test")

        chunks = [
            _event("on_chain_start", "align_agent", node=None),
            _event("on_chain_start", "intent"),
            _event("on_chain_start", "RunnableSequence", node="intent"),
            _event("on_chat_model_start", "ChatGroq", node="intent"),
            _event("on_chat_model_stream", "ChatGroq", node="intent",
                   data={"chunk": {"content": ""}}),
            _event("on_chat_model_end", "ChatGroq", node="intent"),
            _event("on_parser_start", "PydanticToolsParser", node="intent"),
            _event("on_parser_end", "PydanticToolsParser", node="intent"),
            _event("on_chain_end", "RunnableSequence", node="intent"),
            _event("on_chain_start", "should_retrieve", node="intent"),
            _event("on_chain_end", "should_retrieve", node="intent"),
            _event("on_chain_stream", "intent", node="intent"),
            _event("on_chain_end", "intent",
                   data={"output": {"messages": [{"content": "I am a compliance auditor."}]}}),
            _event("on_chain_end", "align_agent", node=None),
        ]

        mock_chunk = MagicMock()
        mock_chunk.data = chunks

        async def mock_stream():
            yield mock_chunk

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            token_events = [e for e in events if "event: token" in e]
            assert len(token_events) == 1, (
                "fallback message should survive nested RunnableSequence/conditional-edge events"
            )
            assert '"data":"I am a compliance auditor."' in token_events[0]

    @pytest.mark.asyncio
    async def test_nested_chat_model_events_do_not_emit_duplicate_start(self):
        """on_chain_start fires for nested runnables too (RunnableSequence inside
        a node) — these must not be mistaken for a second top-level node start."""
        mock_request = MagicMock(session_id="test-session", user_message="test")

        mock_chunk = MagicMock()
        mock_chunk.data = [
            _event("on_chain_start", "generate"),
            _event("on_chain_start", "RunnableSequence", node="generate"),
        ]

        async def mock_stream():
            yield mock_chunk

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = mock_stream()

            events = []
            async for sse_chunk in stream_align(mock_request):
                events.append(sse_chunk)

            start_events = [e for e in events if "event: start" in e]
            assert len(start_events) == 1
            assert '"response_type":"report"' in start_events[0]


class TestStreamFromLangGraphRetry:
    """Verifies the retry-with-backoff decorator itself: a cold-start agent
    that fails to connect a couple of times before waking up should recover
    without the caller ever seeing an exception."""

    @pytest.mark.asyncio
    async def test_retries_and_recovers_from_transient_connect_errors(self):
        call_count = 0

        def flaky_stream(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("agent is still waking up")
            return "connected"

        mock_client = MagicMock()
        mock_client.runs.stream.side_effect = flaky_stream

        with patch("app.services.align_service.get_langgraph_client", return_value=mock_client), \
                patch("asyncio.sleep", new=AsyncMock()):
            result = await _stream_from_langgraph("session-1", "hello")

        assert result == "connected"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_gives_up_after_exhausting_retries(self):
        mock_client = MagicMock()
        mock_client.runs.stream.side_effect = httpx.ConnectError("agent never woke up")

        with patch("app.services.align_service.get_langgraph_client", return_value=mock_client), \
                patch("asyncio.sleep", new=AsyncMock()):
            with pytest.raises(httpx.ConnectError):
                await _stream_from_langgraph("session-1", "hello")

        assert mock_client.runs.stream.call_count == 5
