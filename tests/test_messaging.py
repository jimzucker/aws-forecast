"""Unit tests for send_slack, send_teams, send_sns."""
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import get_forecast
from tests._helpers import make_mock_boto3_session


class SendSlackTests(unittest.TestCase):
    def test_empty_url_is_a_nop(self):
        with patch.object(get_forecast, "urlopen") as urlopen:
            get_forecast.send_slack("", "hello")
            urlopen.assert_not_called()

    def test_posts_json_payload_to_slack(self):
        with patch.object(get_forecast, "urlopen") as urlopen:
            urlopen.return_value.read.return_value = b"ok"
            get_forecast.send_slack("https://hooks.slack.com/X", "hello")
            urlopen.assert_called_once()
            req = urlopen.call_args.args[0]
            self.assertEqual(req.full_url, "https://hooks.slack.com/X")
            self.assertEqual(
                json.loads(req.data.decode("utf-8")),
                {"text": "hello"},
            )

    def test_http_error_is_reraised(self):
        err = HTTPError("url", 500, "boom", hdrs=None, fp=None)
        with patch.object(get_forecast, "urlopen", side_effect=err):
            with self.assertRaises(HTTPError):
                get_forecast.send_slack("https://hooks.slack.com/X", "hi")

    def test_url_error_is_reraised(self):
        with patch.object(get_forecast, "urlopen", side_effect=URLError("dns")):
            with self.assertRaises(URLError):
                get_forecast.send_slack("https://hooks.slack.com/X", "hi")


class SendTeamsTests(unittest.TestCase):
    def test_empty_url_is_a_nop(self):
        with patch.object(get_forecast, "urlopen") as urlopen:
            get_forecast.send_teams("", "hello")
            urlopen.assert_not_called()

    def test_posts_json_payload_to_teams(self):
        with patch.object(get_forecast, "urlopen") as urlopen:
            urlopen.return_value.read.return_value = b"ok"
            get_forecast.send_teams("https://teams.example.com/hook", "hi")
            urlopen.assert_called_once()
            req = urlopen.call_args.args[0]
            self.assertEqual(
                json.loads(req.data.decode("utf-8")),
                {"text": "hi"},
            )

    def test_http_error_is_reraised(self):
        err = HTTPError("url", 500, "boom", hdrs=None, fp=None)
        with patch.object(get_forecast, "urlopen", side_effect=err):
            with self.assertRaises(HTTPError):
                get_forecast.send_teams("https://teams.example.com/hook", "x")

    def test_url_error_is_reraised(self):
        with patch.object(get_forecast, "urlopen", side_effect=URLError("dns")):
            with self.assertRaises(URLError):
                get_forecast.send_teams("https://teams.example.com/hook", "x")


class SendSnsTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()
        self.sns_client = self.session._clients["sns"]

    def test_empty_arn_is_a_nop(self):
        get_forecast.send_sns(self.session, "", "hi")
        self.sns_client.publish.assert_not_called()

    def test_publishes_to_sns(self):
        arn = "arn:aws:sns:us-east-1:123:topic"
        get_forecast.send_sns(self.session, arn, "daily forecast")
        self.sns_client.publish.assert_called_once_with(
            TopicArn=arn, Message="daily forecast"
        )

    def test_publish_exception_is_swallowed(self):
        """send_sns catches and logs; it must not propagate errors."""
        self.sns_client.publish.side_effect = RuntimeError("boom")
        # Should NOT raise.
        get_forecast.send_sns(
            self.session,
            "arn:aws:sns:us-east-1:123:topic",
            "msg",
        )


class PayloadEncodingTests(unittest.TestCase):
    """Regression: Slack/Teams payloads must round-trip through JSON cleanly
    even when the message contains characters that would break naive string
    concatenation (unicode, triple backticks, newlines, large bodies)."""

    def _captured_payload(self, urlopen, expected_url):
        urlopen.assert_called_once()
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, expected_url)
        return json.loads(req.data.decode("utf-8"))

    def test_slack_payload_roundtrips_unicode(self):
        msg = "Account résumé: $1,234 — forecast €5,678 ✓"
        with patch.object(get_forecast, "urlopen") as urlopen:
            urlopen.return_value.read.return_value = b"ok"
            get_forecast.send_slack("https://hooks.slack.com/X", msg)
            payload = self._captured_payload(urlopen, "https://hooks.slack.com/X")
        self.assertEqual(payload, {"text": msg})

    def test_teams_payload_roundtrips_unicode(self):
        msg = "MTD спend: $12,345"
        with patch.object(get_forecast, "urlopen") as urlopen:
            urlopen.return_value.read.return_value = b"ok"
            get_forecast.send_teams("https://teams.example.com/hook", msg)
            payload = self._captured_payload(urlopen, "https://teams.example.com/hook")
        self.assertEqual(payload, {"text": msg})

    def test_slack_payload_with_triple_backticks_and_newlines(self):
        """publish_forecast wraps the table in ``` code fences — make sure the
        Slack payload still serializes when the message body contains them."""
        msg = "```\nAccount      | Forecast | Change\n----------- | -------- | ------\nTotal       | $600     | 100.0%\n```\n"
        with patch.object(get_forecast, "urlopen") as urlopen:
            urlopen.return_value.read.return_value = b"ok"
            get_forecast.send_slack("https://hooks.slack.com/X", msg)
            payload = self._captured_payload(urlopen, "https://hooks.slack.com/X")
        self.assertEqual(payload["text"], msg)
        self.assertIn("```", payload["text"])

    def test_large_payload_is_posted_intact(self):
        msg = "x" * 10_000
        with patch.object(get_forecast, "urlopen") as urlopen:
            urlopen.return_value.read.return_value = b"ok"
            get_forecast.send_slack("https://hooks.slack.com/X", msg)
            payload = self._captured_payload(urlopen, "https://hooks.slack.com/X")
        self.assertEqual(len(payload["text"]), 10_000)


if __name__ == "__main__":
    unittest.main()
