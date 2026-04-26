"""Unit tests for claude_connector_handler.lambda_handler."""
import json
import unittest
from unittest.mock import patch

import claude_connector_handler as handler
from tests._helpers import make_mock_boto3_session


VALID_TOKEN = "expected-bearer-token"

CALC_ROWS = [
    {"account_name": "Total", "amount_usage": 300.0,
     "amount_forecast": 600.0, "forecast_variance": 100.0},
    {"account_name": "alpha", "amount_usage": 100.0,
     "amount_forecast": 200.0, "forecast_variance": 100.0},
    {"account_name": "beta", "amount_usage": 200.0,
     "amount_forecast": 400.0, "forecast_variance": 100.0},
]


def _make_event(authorization=None, include_headers=True):
    event = {"requestContext": {"http": {"method": "POST"}}}
    if include_headers:
        event["headers"] = {}
        if authorization is not None:
            event["headers"]["authorization"] = authorization
    return event


def _patch_session(session):
    return patch.object(handler.boto3.session, "Session", return_value=session)


def _seed_secret(session, token=VALID_TOKEN):
    session._clients["secretsmanager"].get_secret_value.return_value = {
        "SecretString": json.dumps({"claude_bearer_token": token})
    }


class HandlerAuthTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()
        _seed_secret(self.session)

    def test_missing_headers_returns_400(self):
        event = _make_event(include_headers=False)
        with _patch_session(self.session):
            response = handler.lambda_handler(event, None)
        self.assertEqual(response["statusCode"], 400)
        self.assertIn("Malformed", json.loads(response["body"])["error"])

    def test_missing_authorization_header_returns_401(self):
        with _patch_session(self.session):
            response = handler.lambda_handler(_make_event(authorization=None), None)
        self.assertEqual(response["statusCode"], 401)

    def test_malformed_authorization_header_returns_401(self):
        with _patch_session(self.session):
            response = handler.lambda_handler(
                _make_event(authorization="not-a-bearer-token"), None
            )
        self.assertEqual(response["statusCode"], 401)

    def test_wrong_bearer_token_returns_401(self):
        with _patch_session(self.session):
            response = handler.lambda_handler(
                _make_event(authorization="Bearer wrong-token"), None
            )
        self.assertEqual(response["statusCode"], 401)
        self.assertEqual(json.loads(response["body"])["error"], "Invalid bearer token")

    def test_capitalized_authorization_header_works(self):
        event = {"headers": {"Authorization": f"Bearer {VALID_TOKEN}"}}
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=CALC_ROWS):
            response = handler.lambda_handler(event, None)
        self.assertEqual(response["statusCode"], 200)


class HandlerSuccessTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()
        _seed_secret(self.session)

    def test_valid_token_returns_200_and_documented_shape(self):
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=CALC_ROWS):
            response = handler.lambda_handler(
                _make_event(authorization=f"Bearer {VALID_TOKEN}"), None
            )
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"]["Content-Type"], "application/json")
        body = json.loads(response["body"])
        self.assertEqual(set(body.keys()),
                         {"total_mtd", "total_forecast", "percent_change", "accounts"})

    def test_total_row_maps_to_top_level_fields(self):
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=CALC_ROWS):
            response = handler.lambda_handler(
                _make_event(authorization=f"Bearer {VALID_TOKEN}"), None
            )
        body = json.loads(response["body"])
        self.assertEqual(body["total_mtd"], 300.0)
        self.assertEqual(body["total_forecast"], 600.0)
        self.assertEqual(body["percent_change"], 100.0)

    def test_non_total_rows_go_into_accounts_list(self):
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=CALC_ROWS):
            response = handler.lambda_handler(
                _make_event(authorization=f"Bearer {VALID_TOKEN}"), None
            )
        body = json.loads(response["body"])
        names = {a["name"] for a in body["accounts"]}
        self.assertEqual(names, {"alpha", "beta"})
        for a in body["accounts"]:
            self.assertEqual(set(a.keys()), {"name", "mtd", "forecast", "percent_change"})

    def test_no_total_row_falls_back_to_zero_totals(self):
        rows = [r for r in CALC_ROWS if r["account_name"] != "Total"]
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=rows):
            response = handler.lambda_handler(
                _make_event(authorization=f"Bearer {VALID_TOKEN}"), None
            )
        body = json.loads(response["body"])
        self.assertEqual(body["total_mtd"], 0.0)
        self.assertEqual(body["total_forecast"], 0.0)
        self.assertEqual(len(body["accounts"]), 2)


class HandlerFailureTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()
        _seed_secret(self.session)

    def test_calc_forecast_raises_returns_500(self):
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast",
                          side_effect=RuntimeError("boom")):
            response = handler.lambda_handler(
                _make_event(authorization=f"Bearer {VALID_TOKEN}"), None
            )
        self.assertEqual(response["statusCode"], 500)
        body = json.loads(response["body"])
        self.assertEqual(body, {"error": "Cost Explorer unavailable"})
        # No stack trace leaked into the response body.
        self.assertNotIn("Traceback", response["body"])
        self.assertNotIn("boom", response["body"])

    def test_secrets_manager_failure_returns_500(self):
        self.session._clients["secretsmanager"].get_secret_value.side_effect = \
            RuntimeError("secret denied")
        with _patch_session(self.session):
            response = handler.lambda_handler(
                _make_event(authorization=f"Bearer {VALID_TOKEN}"), None
            )
        self.assertEqual(response["statusCode"], 500)
        body = json.loads(response["body"])
        self.assertEqual(body, {"error": "Auth backend unavailable"})


class HandlerSecretRotationTests(unittest.TestCase):
    """Regression: handler must not cache the bearer token across invocations."""

    def test_rotated_secret_is_picked_up_on_next_call(self):
        session = make_mock_boto3_session()
        sm = session._clients["secretsmanager"]

        # First invocation with token "old".
        sm.get_secret_value.return_value = {
            "SecretString": json.dumps({"claude_bearer_token": "old"})
        }
        with _patch_session(session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=CALC_ROWS):
            r1 = handler.lambda_handler(_make_event(authorization="Bearer old"), None)
        self.assertEqual(r1["statusCode"], 200)

        # Rotate. Second invocation with the new token "new".
        sm.get_secret_value.return_value = {
            "SecretString": json.dumps({"claude_bearer_token": "new"})
        }
        with _patch_session(session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=CALC_ROWS):
            r2 = handler.lambda_handler(_make_event(authorization="Bearer new"), None)
            r3 = handler.lambda_handler(_make_event(authorization="Bearer old"), None)
        self.assertEqual(r2["statusCode"], 200)
        self.assertEqual(r3["statusCode"], 401)


if __name__ == "__main__":
    unittest.main()
