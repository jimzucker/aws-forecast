"""Unit tests for get_forecast.get_secret."""
import logging
import unittest
from unittest.mock import MagicMock

import get_forecast
from tests._helpers import assert_records_format_cleanly, logging_enabled


class _FakeClientError(Exception):
    """Stand-in for botocore.exceptions.ClientError exposing the
    ``response`` attribute get_secret inspects."""

    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class GetSecretTests(unittest.TestCase):
    def test_returns_secret_string_on_success(self):
        client = MagicMock()
        client.get_secret_value.return_value = {
            "SecretString": '{"slack_url": "https://x"}'
        }
        self.assertEqual(
            get_forecast.get_secret(client),
            '{"slack_url": "https://x"}',
        )
        client.get_secret_value.assert_called_once_with(
            SecretId=get_forecast.AWSGENIE_SECRET_MANAGER
        )

    def test_invalid_request_exception_returns_empty_string(self):
        client = MagicMock()
        client.get_secret_value.side_effect = _FakeClientError(
            "InvalidRequestException"
        )
        self.assertEqual(get_forecast.get_secret(client), "")

    def test_invalid_parameter_exception_returns_empty_string(self):
        client = MagicMock()
        client.get_secret_value.side_effect = _FakeClientError(
            "InvalidParameterException"
        )
        self.assertEqual(get_forecast.get_secret(client), "")


class GetSecretLogFormattingTests(unittest.TestCase):
    """Regression guard for the line 76 / 78 logger format-string bugs.

    The original code called ``logger.error("prefix:", e)`` with no
    ``%s`` placeholder — at emit time the logging module raises
    ``TypeError: not all arguments converted during string formatting``
    and the exception detail never reaches the log. These tests assert
    the records now render cleanly via ``LogRecord.getMessage`` and
    that the rendered message includes the exception text.
    """

    def test_invalid_request_log_record_formats_and_includes_exception(self):
        client = MagicMock()
        client.get_secret_value.side_effect = _FakeClientError(
            "InvalidRequestException"
        )
        with logging_enabled():
            with self.assertLogs(get_forecast.logger, level=logging.ERROR) as cm:
                get_forecast.get_secret(client)
        assert_records_format_cleanly(self, cm.records)
        self.assertTrue(
            any("invalid due to" in r.getMessage() for r in cm.records),
            f"expected invalid-request log; got: {[r.getMessage() for r in cm.records]}",
        )

    def test_invalid_parameter_log_record_formats_and_includes_exception(self):
        client = MagicMock()
        client.get_secret_value.side_effect = _FakeClientError(
            "InvalidParameterException"
        )
        with logging_enabled():
            with self.assertLogs(get_forecast.logger, level=logging.ERROR) as cm:
                get_forecast.get_secret(client)
        assert_records_format_cleanly(self, cm.records)
        self.assertTrue(
            any("invalid params" in r.getMessage() for r in cm.records),
            f"expected invalid-params log; got: {[r.getMessage() for r in cm.records]}",
        )


if __name__ == "__main__":
    unittest.main()
