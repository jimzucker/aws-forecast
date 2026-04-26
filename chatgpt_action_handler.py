"""
ChatGPT Custom GPT Action Lambda for AWS Cost Summary.

Exposed as a Lambda Function URL. Validates a bearer token from Secrets
Manager (the API Key the GPT builder stores), calls calc_forecast(), and
returns a normalized JSON payload that ChatGPT consumes per the
chatgpt_action_openapi.yaml schema.

Auth: Authorization: Bearer <token> matched against Secrets Manager key
      `chatgpt_bearer_token` in secret `aws_cost_chatgpt_action`.
"""
import json
import logging
import os

import boto3

import get_forecast


logger = logging.getLogger()
logger.setLevel(logging.INFO)


SECRET_NAME_ENV = "CHATGPT_ACTION_SECRET_NAME"
SECRET_KEY_ENV = "CHATGPT_ACTION_SECRET_KEY"
DEFAULT_SECRET_NAME = "aws_cost_chatgpt_action"
DEFAULT_SECRET_KEY = "chatgpt_bearer_token"


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _expected_token(boto3_session):
    """Fetch the expected bearer token from Secrets Manager every call.

    Not cached: a token rotation by the user must take effect on the very
    next invocation. Regression-tested in tests/test_chatgpt_action_handler.py.
    """
    sm = boto3_session.client("secretsmanager")
    secret_name = os.environ.get(SECRET_NAME_ENV, DEFAULT_SECRET_NAME)
    secret_key = os.environ.get(SECRET_KEY_ENV, DEFAULT_SECRET_KEY)
    payload = sm.get_secret_value(SecretId=secret_name)["SecretString"]
    return json.loads(payload)[secret_key]


def _bearer_from_event(event):
    headers = event.get("headers")
    if not isinstance(headers, dict):
        return None
    auth = headers.get("authorization") or headers.get("Authorization")
    if not auth or not isinstance(auth, str):
        return None
    parts = auth.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _to_payload(rows):
    total = next((r for r in rows if r["account_name"] == "Total"), None)
    accounts = [
        {
            "name": r["account_name"],
            "mtd": r["amount_usage"],
            "forecast": r["amount_forecast"],
            "percent_change": r["forecast_variance"],
        }
        for r in rows
        if r["account_name"] != "Total"
    ]
    if total is None:
        return {
            "total_mtd": 0.0,
            "total_forecast": 0.0,
            "percent_change": 0.0,
            "accounts": accounts,
        }
    return {
        "total_mtd": total["amount_usage"],
        "total_forecast": total["amount_forecast"],
        "percent_change": total["forecast_variance"],
        "accounts": accounts,
    }


def lambda_handler(event, context):
    if not isinstance(event, dict) or "headers" not in event:
        return _response(400, {"error": "Malformed event: missing headers"})

    presented = _bearer_from_event(event)
    if presented is None:
        return _response(401, {"error": "Missing or malformed Authorization header"})

    session = boto3.session.Session()

    try:
        expected = _expected_token(session)
    except Exception:
        logger.exception("Failed to fetch bearer token from Secrets Manager")
        return _response(500, {"error": "Auth backend unavailable"})

    if presented != expected:
        return _response(401, {"error": "Invalid bearer token"})

    try:
        rows = get_forecast.calc_forecast(session)
    except Exception:
        logger.exception("calc_forecast failed")
        return _response(500, {"error": "Cost Explorer unavailable"})

    return _response(200, _to_payload(rows))
