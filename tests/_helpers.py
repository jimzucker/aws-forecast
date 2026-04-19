"""Shared helpers and mock factories for the test suite."""
from unittest.mock import MagicMock


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
