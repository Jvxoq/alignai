import logging
from types import SimpleNamespace
from unittest.mock import patch

from pythonjsonlogger.json import JsonFormatter

from app.core.logging import setup_logging


class TestSetupLogging:
    def teardown_method(self):
        logging.getLogger().handlers.clear()

    def test_installs_json_stream_handler(self):
        with patch("app.core.logging.get_settings", return_value=SimpleNamespace(DEBUG=False)):
            setup_logging()

        root = logging.getLogger()
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) == 1
        assert isinstance(stream_handlers[0].formatter, JsonFormatter)

    def test_debug_setting_sets_debug_level(self):
        with patch("app.core.logging.get_settings", return_value=SimpleNamespace(DEBUG=True)):
            setup_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_non_debug_setting_sets_info_level(self):
        with patch("app.core.logging.get_settings", return_value=SimpleNamespace(DEBUG=False)):
            setup_logging()
        assert logging.getLogger().level == logging.INFO

    def test_clears_pre_existing_handlers(self):
        root = logging.getLogger()
        sentinel = logging.NullHandler()
        root.addHandler(sentinel)
        assert sentinel in root.handlers

        with patch("app.core.logging.get_settings", return_value=SimpleNamespace(DEBUG=False)):
            setup_logging()

        assert sentinel not in root.handlers
