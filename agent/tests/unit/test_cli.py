import logging
import sys
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.cli import QUIET_LOGGERS, _quiet_noisy_loggers, main


class TestQuietNoisyLoggers:
    def test_sets_warning_level_on_known_noisy_loggers(self):
        for name in QUIET_LOGGERS:
            logging.getLogger(name).setLevel(logging.DEBUG)

        _quiet_noisy_loggers()

        for name in QUIET_LOGGERS:
            assert logging.getLogger(name).level == logging.WARNING


class TestMain:
    @patch("app.cli.setup_logging")
    @patch("app.cli.graph")
    async def test_query_from_flag_invokes_graph_and_logs_ai_messages(self, mock_graph, mock_setup, monkeypatch, caplog):
        monkeypatch.setattr(sys, "argv", ["cli.py", "-q", "What is Article 5?"])
        mock_graph.ainvoke = AsyncMock(return_value={
            "messages": [
                HumanMessage(content="What is Article 5?"),
                AIMessage(content="Article 5 prohibits certain AI practices."),
            ]
        })

        with caplog.at_level(logging.INFO, logger="app.cli"):
            await main()

        mock_graph.ainvoke.assert_awaited_once()
        called_state = mock_graph.ainvoke.call_args[0][0]
        assert called_state["messages"][0].content == "What is Article 5?"
        assert "Article 5 prohibits certain AI practices." in caplog.text

    @patch("app.cli.setup_logging")
    @patch("app.cli.graph")
    async def test_no_flag_prompts_via_input(self, mock_graph, mock_setup, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["cli.py"])
        monkeypatch.setattr("builtins.input", lambda _: "interactive question")
        mock_graph.ainvoke = AsyncMock(return_value={"messages": []})

        await main()

        mock_graph.ainvoke.assert_awaited_once()
        called_state = mock_graph.ainvoke.call_args[0][0]
        assert called_state["messages"][0].content == "interactive question"

    @patch("app.cli.setup_logging")
    @patch("app.cli.graph")
    async def test_empty_query_exits_without_invoking_graph(self, mock_graph, mock_setup, monkeypatch, caplog):
        monkeypatch.setattr(sys, "argv", ["cli.py", "-q", "   "])
        mock_graph.ainvoke = AsyncMock()

        with caplog.at_level(logging.WARNING, logger="app.cli"):
            await main()

        mock_graph.ainvoke.assert_not_called()
        assert "Empty query" in caplog.text

    @patch("app.cli.setup_logging")
    @patch("app.cli.graph")
    async def test_only_ai_messages_are_logged(self, mock_graph, mock_setup, monkeypatch, caplog):
        monkeypatch.setattr(sys, "argv", ["cli.py", "-q", "hello"])
        mock_graph.ainvoke = AsyncMock(return_value={
            "messages": [
                HumanMessage(content="hello"),
                AIMessage(content="hi there"),
            ]
        })

        with caplog.at_level(logging.INFO, logger="app.cli"):
            await main()

        assert "hi there" in caplog.text
        assert "hello" not in caplog.text
