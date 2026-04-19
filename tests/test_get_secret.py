"""Unit tests for get_forecast.get_secret."""
import unittest
from unittest.mock import MagicMock

import get_forecast


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


if __name__ == "__main__":
    unittest.main()
