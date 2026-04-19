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


if __name__ == "__main__":
    unittest.main()
