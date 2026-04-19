"""Unit tests for get_forecast.publish_forecast."""
import os
import unittest
from unittest.mock import patch

import get_forecast
from tests._helpers import make_mock_boto3_session


SAMPLE_OUTPUT = [
    {"account_name": "Total", "amount_usage": 300.0,
     "amount_forecast": 600.0, "forecast_variance": 100.0},
    {"account_name": "alpha", "amount_usage": 100.0,
     "amount_forecast": 200.0, "forecast_variance": 100.0},
    {"account_name": "beta", "amount_usage": 200.0,
     "amount_forecast": 400.0, "forecast_variance": 100.0},
]


class _EnvScope:
    """Tiny context manager to set/unset env vars around a test."""

    def __init__(self, **overrides):
        self.overrides = overrides
        self.saved = {}

    def __enter__(self):
        for k, v in self.overrides.items():
            self.saved[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, saved in self.saved.items():
            if saved is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = saved
        return False


class PublishForecastDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()

    def test_uses_default_columns_when_env_unset(self):
        with _EnvScope(
            GET_FORECAST_COLUMNS_DISPLAYED=None,
            GET_FORECAST_ACCOUNT_COLUMN_WIDTH=None,
        ):
            with patch.object(get_forecast, "calc_forecast",
                              return_value=SAMPLE_OUTPUT), \
                 patch.object(get_forecast, "display_output") as display:
                get_forecast.publish_forecast(self.session)
                message = display.call_args.args[1]
        # Default columns: Account | Forecast | Change  (no MTD).
        self.assertIn("Account", message)
        self.assertIn("Forecast", message)
        self.assertIn("Change", message)
        self.assertNotIn("MTD", message)
        # Output is wrapped in a triple-backtick code block.
        self.assertTrue(message.startswith("```\n"))
        self.assertTrue(message.rstrip("\n").endswith("```"))

    def test_body_contains_sorted_account_names(self):
        with _EnvScope(GET_FORECAST_COLUMNS_DISPLAYED=None,
                       GET_FORECAST_ACCOUNT_COLUMN_WIDTH=None):
            with patch.object(get_forecast, "calc_forecast",
                              return_value=SAMPLE_OUTPUT), \
                 patch.object(get_forecast, "display_output") as display:
                get_forecast.publish_forecast(self.session)
                message = display.call_args.args[1]
        # Total ($600) > beta ($400) > alpha ($200).
        self.assertLess(message.index("Total"), message.index("beta"))
        self.assertLess(message.index("beta"), message.index("alpha"))


class PublishForecastEnvOverrideTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()

    def test_columns_env_overrides_default(self):
        with _EnvScope(
            GET_FORECAST_COLUMNS_DISPLAYED="Account,MTD,Forecast",
            GET_FORECAST_ACCOUNT_COLUMN_WIDTH=None,
        ):
            with patch.object(get_forecast, "calc_forecast",
                              return_value=SAMPLE_OUTPUT), \
                 patch.object(get_forecast, "display_output") as display:
                get_forecast.publish_forecast(self.session)
                message = display.call_args.args[1]
        self.assertIn("MTD", message)
        self.assertNotIn("Change", message)

    def test_single_column_env(self):
        with _EnvScope(
            GET_FORECAST_COLUMNS_DISPLAYED="Account",
            GET_FORECAST_ACCOUNT_COLUMN_WIDTH=None,
        ):
            with patch.object(get_forecast, "calc_forecast",
                              return_value=SAMPLE_OUTPUT), \
                 patch.object(get_forecast, "display_output") as display:
                get_forecast.publish_forecast(self.session)
                message = display.call_args.args[1]
        body_lines = [
            line for line in message.splitlines()
            if line and not line.startswith("```")
        ]
        for line in body_lines:
            self.assertNotIn(" | ", line)


class PublishForecastIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()

    def test_pipes_calc_output_through_format_rows_into_display(self):
        """Minimal end-to-end wiring check: calc_forecast -> format_rows ->
        display_output are invoked in order and the final message contains
        a header and at least one data row."""
        with _EnvScope(GET_FORECAST_COLUMNS_DISPLAYED=None,
                       GET_FORECAST_ACCOUNT_COLUMN_WIDTH=None):
            with patch.object(get_forecast, "calc_forecast",
                              return_value=SAMPLE_OUTPUT) as calc, \
                 patch.object(get_forecast, "display_output") as display:
                get_forecast.publish_forecast(self.session)
                calc.assert_called_once_with(self.session)
                display.assert_called_once()
                session_arg, message = display.call_args.args
                self.assertIs(session_arg, self.session)
        lines = [
            l for l in message.splitlines()
            if l and not l.startswith("```")
        ]
        # Header + separator + 3 data rows = at least 5 rendered lines.
        self.assertGreaterEqual(len(lines), 5)


if __name__ == "__main__":
    unittest.main()
