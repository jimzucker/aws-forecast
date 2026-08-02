"""Unit tests for get_forecast.display_output."""
import io
import json
import logging
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import get_forecast
from tests._helpers import (
    assert_records_format_cleanly,
    logging_enabled,
    make_mock_boto3_session,
)


class DisplayOutputTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()
        self.secrets = self.session._clients["secretsmanager"]

    def _capture(self, fn, *args, **kwargs):
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args, **kwargs)
        return buf.getvalue()

    def test_prints_message_always(self):
        with patch.object(get_forecast, "send_slack") as ss, \
             patch.object(get_forecast, "send_teams") as st, \
             patch.object(get_forecast, "send_sns") as sn:
            stdout = self._capture(
                get_forecast.display_output, self.session, "hello"
            )
            self.assertIn("hello", stdout)
            # Secret payload is "{}" so none of the publishers should fire.
            ss.assert_not_called()
            st.assert_not_called()
            sn.assert_not_called()

    def test_dispatches_to_slack_when_url_present(self):
        self.secrets.get_secret_value.return_value = {
            "SecretString": json.dumps({"slack_url": "https://slack/x"})
        }
        with patch.object(get_forecast, "send_slack") as ss, \
             patch.object(get_forecast, "send_teams") as st, \
             patch.object(get_forecast, "send_sns") as sn:
            self._capture(get_forecast.display_output, self.session, "msg")
            ss.assert_called_once_with("https://slack/x", "msg")
            st.assert_not_called()
            sn.assert_not_called()

    def test_dispatches_to_teams_when_url_present(self):
        self.secrets.get_secret_value.return_value = {
            "SecretString": json.dumps({"teams_url": "https://teams/x"})
        }
        with patch.object(get_forecast, "send_slack") as ss, \
             patch.object(get_forecast, "send_teams") as st, \
             patch.object(get_forecast, "send_sns") as sn:
            self._capture(get_forecast.display_output, self.session, "msg")
            st.assert_called_once_with("https://teams/x", "msg")
            ss.assert_not_called()
            sn.assert_not_called()

    def test_dispatches_to_sns_when_arn_present(self):
        self.secrets.get_secret_value.return_value = {
            "SecretString": json.dumps({"sns_arn": "arn:aws:sns:us-east-1:1:t"})
        }
        with patch.object(get_forecast, "send_slack") as ss, \
             patch.object(get_forecast, "send_teams") as st, \
             patch.object(get_forecast, "send_sns") as sn:
            self._capture(get_forecast.display_output, self.session, "msg")
            sn.assert_called_once_with(
                self.session, "arn:aws:sns:us-east-1:1:t", "msg"
            )
            ss.assert_not_called()
            st.assert_not_called()

    def test_dispatches_to_all_three_when_all_configured(self):
        self.secrets.get_secret_value.return_value = {
            "SecretString": json.dumps({
                "slack_url": "https://slack/x",
                "teams_url": "https://teams/x",
                "sns_arn": "arn:aws:sns:us-east-1:1:t",
            })
        }
        with patch.object(get_forecast, "send_slack") as ss, \
             patch.object(get_forecast, "send_teams") as st, \
             patch.object(get_forecast, "send_sns") as sn:
            self._capture(get_forecast.display_output, self.session, "msg")
            ss.assert_called_once()
            st.assert_called_once()
            sn.assert_called_once()

    def test_secret_fetch_failure_still_prints(self):
        """If Secrets Manager blows up, display_output still prints the message."""
        self.secrets.get_secret_value.side_effect = RuntimeError("denied")
        with patch.object(get_forecast, "send_slack"), \
             patch.object(get_forecast, "send_teams"), \
             patch.object(get_forecast, "send_sns"):
            stdout = self._capture(
                get_forecast.display_output, self.session, "still-prints"
            )
            self.assertIn("still-prints", stdout)

    def test_teams_not_configured_log_record_formats_cleanly(self):
        """Regression guard for the line 167 logger format-string bug.

        When the secret JSON has no ``teams_url`` key, display_output hits
        ``logger.info("Disabling Teams, URL not found: %s", e)``. Prior
        to the fix the format string had no placeholder and passing the
        exception as a positional arg raised TypeError at emit time.
        """
        self.secrets.get_secret_value.return_value = {
            "SecretString": json.dumps({"slack_url": "https://slack/x"})
        }
        with patch.object(get_forecast, "send_slack"), \
             patch.object(get_forecast, "send_teams"), \
             patch.object(get_forecast, "send_sns"):
            with logging_enabled():
                with self.assertLogs(get_forecast.logger, level=logging.INFO) as cm:
                    self._capture(
                        get_forecast.display_output, self.session, "msg"
                    )
        assert_records_format_cleanly(self, cm.records)
        self.assertTrue(
            any("Disabling Teams" in r.getMessage() for r in cm.records),
            f"expected Teams-disabled log; got: {[r.getMessage() for r in cm.records]}",
        )


if __name__ == "__main__":
    unittest.main()
