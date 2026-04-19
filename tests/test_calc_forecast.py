"""Unit tests for get_forecast.calc_forecast.

These tests stub the Cost Explorer and Organizations clients so the math
and control-flow branches can be exercised without any real AWS calls.
"""
import unittest

import get_forecast
from tests._helpers import (
    forecast_response,
    grouped_usage_response,
    make_mock_boto3_session,
    usage_response,
)


class CalcForecastHappyPathTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()
        self.ce = self.session._clients["ce"]
        self.org = self.session._clients["organizations"]

    def test_single_account_totals_and_per_account(self):
        # Sequence of get_cost_and_usage calls:
        #   1. total MTD          -> $500
        #   2. prior month total  -> $400
        #   3. grouped by account -> [("111", $500)]
        #   4. prior month for account 111 -> $400
        self.ce.get_cost_and_usage.side_effect = [
            usage_response("500.00"),
            usage_response("400.00"),
            grouped_usage_response([("111111111111", "500.00")]),
            usage_response("400.00"),
        ]
        # Two get_cost_forecast calls: total, then per-account.
        self.ce.get_cost_forecast.side_effect = [
            forecast_response("1000.00"),
            forecast_response("1000.00"),
        ]
        self.org.describe_account.return_value = {"Account": {"Name": "prod"}}

        output = get_forecast.calc_forecast(self.session)

        self.assertEqual(len(output), 2)
        total, prod = output
        self.assertEqual(total["account_name"], "Total")
        self.assertEqual(total["amount_usage"], 500.0)
        self.assertEqual(total["amount_forecast"], 1000.0)
        # (1000 - 400) / 400 * 100 = 150%
        self.assertAlmostEqual(total["forecast_variance"], 150.0, places=4)

        self.assertEqual(prod["account_name"], "prod")
        self.assertEqual(prod["amount_usage"], 500.0)
        self.assertEqual(prod["amount_forecast"], 1000.0)
        self.assertAlmostEqual(prod["forecast_variance"], 150.0, places=4)

    def test_zero_prior_month_variance_defaults_to_100(self):
        self.ce.get_cost_and_usage.side_effect = [
            usage_response("100.00"),   # MTD total
            usage_response("0.00"),     # prior month total — zero
            grouped_usage_response([("111", "100.00")]),
            usage_response("0.00"),     # prior month per-account — zero
        ]
        self.ce.get_cost_forecast.side_effect = [
            forecast_response("200.00"),
            forecast_response("200.00"),
        ]
        self.org.describe_account.return_value = {"Account": {"Name": "new"}}

        output = get_forecast.calc_forecast(self.session)
        # With prior-month == 0 the function leaves variance at its sentinel 100.
        self.assertEqual(output[0]["forecast_variance"], 100)
        self.assertEqual(output[1]["forecast_variance"], 100)


class CalcForecastFallbackTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()
        self.ce = self.session._clients["ce"]
        self.org = self.session._clients["organizations"]

    def test_prior_month_lookup_failure_defaults_to_zero(self):
        """If the prior-month cost_and_usage call raises, variance is
        computed against 0 (so the sentinel 100 is kept)."""
        self.ce.get_cost_and_usage.side_effect = [
            usage_response("500.00"),        # MTD total
            RuntimeError("prior failed"),    # prior month total — boom
            grouped_usage_response([("111", "500.00")]),
            usage_response("400.00"),        # per-account prior
        ]
        self.ce.get_cost_forecast.side_effect = [
            forecast_response("800.00"),
            forecast_response("800.00"),
        ]
        self.org.describe_account.return_value = {"Account": {"Name": "prod"}}

        output = get_forecast.calc_forecast(self.session)
        total = output[0]
        # Prior failed -> sentinel variance of 100.
        self.assertEqual(total["forecast_variance"], 100)

    def test_forecast_call_failure_falls_back_to_usage(self):
        """Weekend / new-account forecast failure should fall back to
        using MTD usage as the forecast amount."""
        self.ce.get_cost_and_usage.side_effect = [
            usage_response("500.00"),
            usage_response("400.00"),
            grouped_usage_response([("111", "500.00")]),
            usage_response("400.00"),
        ]
        # Both forecast calls fail -> amount_forecast must equal amount_usage.
        self.ce.get_cost_forecast.side_effect = [
            RuntimeError("weekend edge case"),
            RuntimeError("new account"),
        ]
        self.org.describe_account.return_value = {"Account": {"Name": "prod"}}

        output = get_forecast.calc_forecast(self.session)
        for row in output:
            self.assertEqual(row["amount_forecast"], row["amount_usage"])
            self.assertEqual(row["amount_forecast"], 500.0)


class CalcForecastPaginationTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()
        self.ce = self.session._clients["ce"]
        self.org = self.session._clients["organizations"]

    def test_handles_next_page_token_across_multiple_pages(self):
        # Two pages of accounts, then prior-month lookups for each.
        self.ce.get_cost_and_usage.side_effect = [
            usage_response("1000.00"),                       # 1. MTD total
            usage_response("800.00"),                        # 2. prior total
            grouped_usage_response(                          # 3. page 1
                [("111", "400.00")], next_token="page-2"),
            grouped_usage_response(                          # 4. page 2
                [("222", "600.00")]),
            usage_response("300.00"),                        # 5. prior 111
            usage_response("500.00"),                        # 6. prior 222
        ]
        self.ce.get_cost_forecast.side_effect = [
            forecast_response("2000.00"),                    # total forecast
            forecast_response("800.00"),                     # 111 forecast
            forecast_response("1200.00"),                    # 222 forecast
        ]
        self.org.describe_account.side_effect = [
            {"Account": {"Name": "alpha"}},
            {"Account": {"Name": "beta"}},
        ]

        output = get_forecast.calc_forecast(self.session)
        names = [row["account_name"] for row in output]
        self.assertEqual(names, ["Total", "alpha", "beta"])
        # Ensure both pages of get_cost_and_usage were consumed.
        self.assertEqual(self.ce.get_cost_and_usage.call_count, 6)


if __name__ == "__main__":
    unittest.main()
