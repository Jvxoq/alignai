import asyncio
import logging

from langchain_core.messages import HumanMessage

from app.core.logging import setup_logging
from app.graph.graph import graph

logger = logging.getLogger(__name__)


QUIET_LOGGERS = ("httpx", "httpcore", "groq", "urllib3", "openai")


def _quiet_noisy_loggers() -> None:
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


async def main() -> None:
    setup_logging()
    _quiet_noisy_loggers()

    import argparse

    parser = argparse.ArgumentParser(description="Run the AlignAI agent from the terminal.")
    parser.add_argument(
        "-q", "--query",
        type=str,
        help="EU AI Act compliance query (omit for interactive prompt)",
    )
    args = parser.parse_args()

    query = args.query
    if not query:
        query = input("> ")

    if not query.strip():
        logger.warning("Empty query — exiting")
        return

    initial_state = {"messages": [HumanMessage(content=query)]}
    result = await graph.ainvoke(initial_state)

    for msg in result.get("messages", []):
        if hasattr(msg, "type") and msg.type == "ai":
            logger.info(msg.content)


if __name__ == "__main__":
    asyncio.run(main())
