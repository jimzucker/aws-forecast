"""Shared helpers and mock factories for the test suite."""
import logging
from contextlib import contextmanager
from unittest.mock import MagicMock


@contextmanager
def logging_enabled(level=logging.DEBUG):
    """Temporarily re-enable logging that ``tests/__init__.py`` disabled.

    The test bootstrap calls ``logging.disable(CRITICAL)`` to keep
    exception-path tests quiet. Some tests, however, need to *capture*
    log records (e.g. to assert a logger.error call formats cleanly
    without raising TypeError). Use this context manager together with
    ``TestCase.assertLogs`` to turn logging back on for the duration of
    a block.
    """
    previous = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    try:
        yield
    finally:
        logging.disable(previous)


def assert_records_format_cleanly(test_case, records):
    """Assert every LogRecord renders via ``getMessage()`` without raising.

    This catches the classic ``logger.error("prefix:", e)`` bug where the
    format string has no ``%s`` placeholder but positional args were
    supplied — ``LogRecord.getMessage`` raises ``TypeError`` in that
    case and the real exception detail is lost.
    """
    for record in records:
        try:
            rendered = record.getMessage()
        except TypeError as exc:  # pragma: no cover - diagnostic path
            test_case.fail(
                "Log record did not format cleanly: "
                f"fmt={record.msg!r} args={record.args!r} error={exc}"
            )
        test_case.assertIsInstance(rendered, str)


def make_mock_boto3_session():
    """Return a MagicMock boto3 Session whose ``.client(name)`` returns
    a consistent sub-client mock per name. Sub-clients are addressable
    via ``session._clients[name]`` for per-test customization.
    """
    session = MagicMock(name="boto3_session")

    ce = MagicMock(name="ce_client")
    ce.get_cost_and_usage.return_value = {
        "ResultsByTime": [
            {"Total": {"UnblendedCost": {"Amount": "500.00", "Unit": "USD"}}}
        ]
    }
    ce.get_cost_forecast.return_value = {
        "Total": {"Amount": "1000.00", "Unit": "USD"}
    }

    org = MagicMock(name="org_client")
    org.describe_account.return_value = {"Account": {"Name": "TestAccount"}}

    sts = MagicMock(name="sts_client")
    sts.get_caller_identity.return_value = {"Account": "123456789012"}

    secrets = MagicMock(name="secrets_client")
    secrets.get_secret_value.return_value = {"SecretString": "{}"}

    sns = MagicMock(name="sns_client")
    sns.publish.return_value = {"MessageId": "abc-123"}

    clients = {
        "ce": ce,
        "organizations": org,
        "sts": sts,
        "secretsmanager": secrets,
        "sns": sns,
    }

    def _client(name, *args, **kwargs):
        return clients[name]

    session.client.side_effect = _client
    session._clients = clients
    return session


def usage_response(amount):
    """Shape returned by ce.get_cost_and_usage without GroupBy."""
    return {
        "ResultsByTime": [
            {"Total": {"UnblendedCost": {"Amount": str(amount), "Unit": "USD"}}}
        ]
    }


def grouped_usage_response(accounts, next_token=None):
    """Shape returned by ce.get_cost_and_usage with GroupBy=LINKED_ACCOUNT.

    ``accounts`` is a list of (account_id, amount) tuples.
    """
    groups = [
        {
            "Keys": [acct_id],
            "Metrics": {"UnblendedCost": {"Amount": str(amt), "Unit": "USD"}},
        }
        for acct_id, amt in accounts
    ]
    response = {"ResultsByTime": [{"Groups": groups}]}
    if next_token:
        response["NextPageToken"] = next_token
    return response


def forecast_response(amount):
    return {"Total": {"Amount": str(amount), "Unit": "USD"}}
