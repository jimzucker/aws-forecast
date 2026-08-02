"""Unit tests for get_forecast.format_rows."""
import unittest

import get_forecast


def _heading(rows):
    return rows[0]


def _separator(rows):
    return rows[1]


def _data_rows(rows):
    return rows[2:]


class FormatRowsHeaderTests(unittest.TestCase):
    def test_returns_header_as_first_row(self):
        rows = get_forecast.format_rows([], account_width=12)
        self.assertEqual(
            _heading(rows),
            {
                "Account": "Account".ljust(12),
                "MTD": "MTD".ljust(8),
                "Forecast": "Forecast".ljust(8),
                "Change": "Change".ljust(8),
            },
        )

    def test_returns_separator_as_second_row(self):
        rows = get_forecast.format_rows([], account_width=12)
        sep = _separator(rows)
        self.assertEqual(sep["Account"], "-" * 12)
        self.assertEqual(sep["MTD"], "-" * 8)
        self.assertEqual(sep["Forecast"], "-" * 8)
        self.assertEqual(sep["Change"], "-" * 8)

    def test_empty_input_produces_only_header_and_separator(self):
        rows = get_forecast.format_rows([], account_width=12)
        self.assertEqual(len(rows), 2)


class FormatRowsSingleAccountTests(unittest.TestCase):
    def test_single_account_formatting(self):
        output = [{
            "account_name": "prod",
            "amount_usage": 100.0,
            "amount_forecast": 200.0,
            "forecast_variance": 25.5,
        }]
        rows = _data_rows(get_forecast.format_rows(output, account_width=10))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["Account"], "prod".ljust(10))
        self.assertEqual(row["MTD"], "$100".ljust(8))
        self.assertEqual(row["Forecast"], "$200".ljust(8))
        self.assertEqual(row["Change"], "25.5%".ljust(8))

    def test_large_dollar_amounts_use_thousands_separator(self):
        output = [{
            "account_name": "big",
            "amount_usage": 12345.67,
            "amount_forecast": 98765.43,
            "forecast_variance": 100.0,
        }]
        row = _data_rows(get_forecast.format_rows(output, account_width=10))[0]
        self.assertIn("$12,346", row["MTD"])
        self.assertIn("$98,765", row["Forecast"])

    def test_negative_variance_is_rendered(self):
        output = [{
            "account_name": "shrink",
            "amount_usage": 10.0,
            "amount_forecast": 5.0,
            "forecast_variance": -37.2,
        }]
        row = _data_rows(get_forecast.format_rows(output, account_width=10))[0]
        self.assertIn("-37.2%", row["Change"])


class FormatRowsTotalSuppressionTests(unittest.TestCase):
    def test_total_is_dropped_when_only_one_real_account(self):
        output = [
            {"account_name": "Total", "amount_usage": 100.0,
             "amount_forecast": 200.0, "forecast_variance": 10.0},
            {"account_name": "solo", "amount_usage": 100.0,
             "amount_forecast": 200.0, "forecast_variance": 10.0},
        ]
        rows = _data_rows(get_forecast.format_rows(output, account_width=10))
        names = [r["Account"].strip() for r in rows]
        self.assertNotIn("Total", names)
        self.assertIn("solo", names)

    def test_total_is_kept_when_there_are_multiple_accounts(self):
        output = [
            {"account_name": "Total", "amount_usage": 300.0,
             "amount_forecast": 600.0, "forecast_variance": 10.0},
            {"account_name": "a", "amount_usage": 100.0,
             "amount_forecast": 200.0, "forecast_variance": 10.0},
            {"account_name": "b", "amount_usage": 200.0,
             "amount_forecast": 400.0, "forecast_variance": 10.0},
        ]
        rows = _data_rows(get_forecast.format_rows(output, account_width=10))
        names = [r["Account"].strip() for r in rows]
        self.assertIn("Total", names)
        self.assertIn("a", names)
        self.assertIn("b", names)


class FormatRowsOrderingTests(unittest.TestCase):
    def test_rows_are_sorted_by_forecast_descending(self):
        output = [
            {"account_name": "Total", "amount_usage": 0.0,
             "amount_forecast": 999.0, "forecast_variance": 0.0},
            {"account_name": "small", "amount_usage": 0.0,
             "amount_forecast": 10.0, "forecast_variance": 0.0},
            {"account_name": "big", "amount_usage": 0.0,
             "amount_forecast": 500.0, "forecast_variance": 0.0},
            {"account_name": "mid", "amount_usage": 0.0,
             "amount_forecast": 100.0, "forecast_variance": 0.0},
        ]
        rows = _data_rows(get_forecast.format_rows(output, account_width=10))
        ordered = [r["Account"].strip() for r in rows]
        self.assertEqual(ordered, ["Total", "big", "mid", "small"])


class FormatRowsAccountWidthTests(unittest.TestCase):
    def test_long_account_name_is_truncated(self):
        output = [{
            "account_name": "averyLongAccountName",
            "amount_usage": 0.0,
            "amount_forecast": 0.0,
            "forecast_variance": 0.0,
        }]
        row = _data_rows(get_forecast.format_rows(output, account_width=8))[0]
        self.assertEqual(row["Account"], "averyLon")
        self.assertEqual(len(row["Account"]), 8)

    def test_short_account_name_is_left_padded(self):
        output = [{
            "account_name": "a",
            "amount_usage": 0.0,
            "amount_forecast": 0.0,
            "forecast_variance": 0.0,
        }]
        row = _data_rows(get_forecast.format_rows(output, account_width=6))[0]
        self.assertEqual(row["Account"], "a".ljust(6))


if __name__ == "__main__":
    unittest.main()
