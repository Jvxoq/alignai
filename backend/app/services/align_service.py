import logging
from collections.abc import AsyncGenerator
from typing import Literal

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.infrastructure.langgraph_client import get_langgraph_client
from app.models.requests import AlignRequest
from app.models.responses import DoneEvent, ErrorEvent, SSEEvent, StartEvent, StatusEvent, TokenEvent

logger = logging.getLogger(__name__)

_NODE_RESPONSE_TYPE: dict[str, Literal["report", "chat", "failure"]] = {
    "generate": "report",
    "fallback": "failure",
}

_NODE_STATUS_MESSAGE: dict[str, str] = {
    "retrieve": "Retrieving documents...",
    "rewrite_objective": "Refining search objective...",
}

_SSE_START_NODES = set(_NODE_RESPONSE_TYPE)
_SSE_STATUS_NODES = set(_NODE_STATUS_MESSAGE)

_STREAMING_NODES = {"generate"}
_FINAL_TOKEN_NODES = {"fallback", "intent"}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    reraise=True,
)
async def _stream_from_langgraph(
    thread_id: str, message: str
):
    client = get_langgraph_client()
    return client.runs.stream(
        thread_id=thread_id,
        assistant_id="align_agent",
        input={"messages": [{"role": "user", "content": message}]},
        stream_mode=["events"],
        if_not_exists="create",
    )


def _format_sse(event: SSEEvent) -> str:
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"


def _extract_message_text(data: dict) -> str:
    """Extract text from a node's on_chain_end output messages."""
    output = data.get("output", {})
    if isinstance(output, str):
        return output
    if not isinstance(output, dict):
        return ""
    messages = output.get("messages", [])
    if not messages:
        return ""
    last_msg = messages[-1]
    if hasattr(last_msg, "content"):
        return last_msg.content
    if isinstance(last_msg, dict):
        return last_msg.get("content", "")
    return ""


async def stream_align(request: AlignRequest) -> AsyncGenerator[str, None]:
    emitted_start = False
    streamed_tokens = False

    try:
        stream = await _stream_from_langgraph(request.session_id, request.user_message)
        async for chunk in stream:
            if chunk.data is None:
                continue

            events = chunk.data
            if not isinstance(events, list):
                events = [events]

            for event in events:
                kind = event.get("event", "")
                name = event.get("name", "")
                # langgraph_node identifies the owning top-level graph node for every
                # event, including ones from nested runnables (LLM calls, parsers,
                # conditional edges) invoked inside a node. A bare on_chain_start/end
                # "name" match is not enough — those nested runnables emit their own
                # on_chain_start/on_chain_end pairs that would otherwise be mistaken
                # for node boundaries and corrupt tracking.
                current_node = event.get("metadata", {}).get("langgraph_node")
                is_node_boundary = name == current_node

                if kind == "on_chain_start" and is_node_boundary:
                    if name in _SSE_START_NODES and not emitted_start:
                        yield _format_sse(StartEvent(response_type=_NODE_RESPONSE_TYPE[name]))
                        emitted_start = True
                    if name in _SSE_STATUS_NODES:
                        yield _format_sse(StatusEvent(message=_NODE_STATUS_MESSAGE[name]))

                elif kind == "on_chat_model_stream":
                    if current_node in _STREAMING_NODES:
                        content = event.get("data", {}).get("chunk", {})
                        if isinstance(content, dict):
                            text = content.get("content", "")
                        elif hasattr(content, "content"):
                            text = content.content
                        else:
                            text = ""
                        if text:
                            streamed_tokens = True
                            yield _format_sse(TokenEvent(data=text))

                elif kind == "on_chain_end" and is_node_boundary:
                    if name == "intent" and not emitted_start:
                        # The graph always starts at "intent", so its
                        # response_type can't be known until it finishes:
                        # if it set an objective, the run continues to
                        # retrieve/generate (or eventually fallback) rather
                        # than answering directly. Only emit "chat" here,
                        # once we know intent's own message is the final one.
                        output = event.get("data", {}).get("output") or {}
                        if isinstance(output, dict) and not output.get("objective"):
                            yield _format_sse(StartEvent(response_type="chat"))
                            emitted_start = True

                    if name in _FINAL_TOKEN_NODES and not streamed_tokens:
                        text = _extract_message_text(event.get("data", {}))
                        if text:
                            yield _format_sse(TokenEvent(data=text))
                    streamed_tokens = False

        yield _format_sse(DoneEvent())

    except (ConnectionError, TimeoutError, OSError) as exc:
        logger.exception("LangGraph stream failed after retries")
        if isinstance(exc, TimeoutError):
            yield _format_sse(ErrorEvent(code=504, message="LangGraph server timeout"))
        else:
            yield _format_sse(ErrorEvent(code=503, message="LangGraph server unavailable"))

    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int) and status_code >= 500:
            logger.exception("LangGraph stream failed with server error")
            yield _format_sse(ErrorEvent(code=503, message="LangGraph server unavailable"))
        else:
            logger.exception("LangGraph stream failed")
            yield _format_sse(ErrorEvent(code=500, message="Internal server error"))
