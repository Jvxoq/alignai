"""Recorded-cassette contract tests for stream_align().

Unlike test_align_service.py (which hand-builds minimal fake events), these
tests replay event sequences captured from a real `langgraph dev` run against
the actual compiled agent graph (see scripts used during the investigation —
fixtures live in tests/fixtures/langgraph_events/). They exist to catch drift
between what we assume the LangGraph SDK emits and what it actually emits —
exactly the class of bug that caused fallback/general-chat messages to be
silently dropped in production (nested runnable events were mistaken for
node boundaries).

Fixtures are trimmed to the fields stream_align() actually reads
(event/name/metadata.langgraph_node, plus chunk content / final output text)
to keep them small while preserving the real event order and shape.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.align_service import stream_align

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "langgraph_events"


def _load_cassette(name: str) -> list[dict]:
    return json.loads((_FIXTURES_DIR / f"{name}.json").read_text())


def _mock_stream_from_cassette(events: list[dict]):
    async def mock_stream():
        for event in events:
            chunk = MagicMock()
            chunk.data = [event]
            yield chunk

    return mock_stream()


class TestStreamAlignCassettes:
    @pytest.mark.asyncio
    async def test_general_chat_fallback_emits_message_token(self):
        """Regression guard: a general (non-compliance) query is handled
        entirely inside the intent node, which internally invokes an LLM
        (call_llm_structured) before returning its own response. That nested
        LLM call's on_chain_start/on_chain_end pairs must not be mistaken for
        the intent node's own boundary — otherwise the response is dropped."""
        cassette = _load_cassette("general_chat_fallback")

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = _mock_stream_from_cassette(cassette)

            events = [chunk async for chunk in stream_align(MagicMock(
                session_id="test-session", user_message="What is the weather in Paris?",
            ))]

        start_events = [e for e in events if "event: start" in e]
        token_events = [e for e in events if "event: token" in e]
        done_events = [e for e in events if "event: done" in e]
        error_events = [e for e in events if "event: error" in e]

        assert len(start_events) == 1
        assert '"response_type":"chat"' in start_events[0]
        assert len(token_events) == 1, (
            "general-chat response must produce exactly one token event "
            "(this is the exact case that was silently dropping the message)"
        )
        assert token_events[0].count('"data":""') == 0, "token text must not be empty"
        assert len(done_events) == 1
        assert len(error_events) == 0

    @pytest.mark.asyncio
    async def test_compliance_report_streams_tokens_and_completes(self):
        """A full compliance query: intent -> retrieve -> generate. Tokens
        should stream incrementally from the generate node's chat model."""
        cassette = _load_cassette("compliance_report")

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = _mock_stream_from_cassette(cassette)

            events = [chunk async for chunk in stream_align(MagicMock(
                session_id="test-session",
                user_message="What does Article 9 say about risk management for high-risk AI systems?",
            ))]

        start_events = [e for e in events if "event: start" in e]
        status_events = [e for e in events if "event: status" in e]
        token_events = [e for e in events if "event: token" in e]
        done_events = [e for e in events if "event: done" in e]
        error_events = [e for e in events if "event: error" in e]

        assert len(start_events) == 1
        assert len(status_events) == 1, "expected exactly one 'Retrieving documents...' status"
        assert len(token_events) > 50, "compliance report should stream many incremental tokens"
        assert len(done_events) == 1
        assert len(error_events) == 0

        # The intent node sets an objective for compliance queries, so its
        # own on_chain_end must NOT emit a "chat" start — the actual start
        # is deferred until "generate" begins, correctly reporting "report".
        # (Previously this was always "chat", breaking the frontend's
        # ReportDocument view — see git history for the regression.)
        assert '"response_type":"report"' in start_events[0]

    @pytest.mark.asyncio
    async def test_low_relevance_query_rewrites_objective_then_generates(self):
        """A compliance-flavored query with no good matches: intent ->
        retrieve -> rewrite_objective -> retrieve -> generate. Verifies the
        rewrite status message appears and the run still completes cleanly."""
        cassette = _load_cassette("low_relevance_rewrite")

        with patch("app.services.align_service._stream_from_langgraph") as mock_langgraph:
            mock_langgraph.return_value = _mock_stream_from_cassette(cassette)

            events = [chunk async for chunk in stream_align(MagicMock(
                session_id="test-session",
                user_message="What does Article 999 of the EU AI Act say about teleportation device compliance audits?",
            ))]

        status_events = [e for e in events if "event: status" in e]
        token_events = [e for e in events if "event: token" in e]
        done_events = [e for e in events if "event: done" in e]
        error_events = [e for e in events if "event: error" in e]

        start_events = [e for e in events if "event: start" in e]
        status_messages = "".join(status_events)
        assert "Retrieving documents..." in status_messages
        assert "Refining search objective..." in status_messages
        assert len(start_events) == 1
        assert '"response_type":"report"' in start_events[0]
        assert len(token_events) > 0
        assert len(done_events) == 1
        assert len(error_events) == 0
