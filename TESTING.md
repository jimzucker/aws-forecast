# Test suite

Unit tests for `get_forecast.py`. All AWS interactions are mocked via
`unittest.mock`, so the suite runs offline with no AWS credentials.

## Layout

```
tests/
  __init__.py           sys.path + offline boto3 stub, log silencing
  _helpers.py           shared mock Session factory and CE response builders
  conftest.py           placeholder (pytest discovers tests/ as a package)
  test_format_rows.py
  test_messaging.py     send_slack / send_teams / send_sns
  test_get_secret.py
  test_display_output.py
  test_calc_forecast.py happy path, pagination, fallbacks
  test_publish_forecast.py env overrides + wiring
  test_entrypoints.py   lambda_handler + main (incl. GET_FORECAST_AWS_PROFILE)
```

54 tests total.

## Running

### With the stdlib runner (zero dependencies)

```bash
python3 -m unittest discover -v
```

Works even without `boto3` or `pytest` installed — the test package stubs
`boto3` / `botocore.exceptions` when they're missing.

### With pytest

```bash
pip install -r requirements-dev.txt
pytest
```

Pytest auto-discovers the `unittest.TestCase` classes. `requirements-dev.txt`
pins `boto3` so the real SDK is used (the stubs stay dormant).

## Coverage targets per module

| Function            | Tests                                                            |
| ------------------- | ---------------------------------------------------------------- |
| `format_rows`       | header/separator shape, sorting, Total suppression, truncation, negative variance, thousands separators |
| `send_slack`        | empty URL is no-op, JSON payload shape, HTTPError/URLError re-raise |
| `send_teams`        | same cases as `send_slack`                                       |
| `send_sns`          | empty ARN no-op, publish call, exception is swallowed            |
| `get_secret`        | success, `InvalidRequestException`, `InvalidParameterException`  |
| `display_output`    | always prints, per-channel dispatch, all-three dispatch, secret fetch failure still prints |
| `calc_forecast`     | single-account totals, zero prior month → sentinel 100, prior-month lookup failure, forecast failure → fallback to usage, describe_account failure → fallback to linked-account id, multi-page pagination |
| `publish_forecast`  | default columns, custom column env var, single-column env, message order follows forecast desc, GET_FORECAST_ACCOUNT_COLUMN_WIDTH coercion (int, non-numeric, zero/negative, unset) |
| `lambda_handler`    | delegates to `publish_forecast`, wraps errors in a generic exception |
| `main`              | exits 0 on success, uses `GET_FORECAST_AWS_PROFILE`, exits 1 on failure |

## Notes on bugs exposed by the suite

While writing these tests a few latent issues surfaced in `get_forecast.py`.

**Fixed:**

- **`describe_account` fallback** (around line 313) — the original code caught
  `AWSOrganizationsNotInUseException`, a name that was never imported, so any
  failure from `org.describe_account` raised `NameError` and aborted the whole
  forecast run. Broadened to `except Exception` (matching the file's existing
  style), which also covers missing IAM permission, throttling, and closed
  accounts. Guarded by
  `test_describe_account_failure_falls_back_to_account_id`.
- **`GET_FORECAST_ACCOUNT_COLUMN_WIDTH` coercion** — `publish_forecast` read
  the env var as a string and passed it straight to `str.ljust`, which
  requires an int, so any non-default value raised `TypeError`. Now parsed
  via `int()` with a warning + fallback to the default of 12 on non-numeric
  or non-positive input. Guarded by the four tests in
  `PublishForecastAccountWidthTests`.
- **Logger format-string mismatches (lines 76, 78, 167)** —
  `logger.error("The request was invalid due to:", e)`,
  `logger.error("The request had invalid params:", e)`, and
  `logger.info("Disabling Teams, URL not found", e)` all passed a
  positional argument with no `%s` placeholder in the format string, so
  the logging module raised `TypeError: not all arguments converted
  during string formatting` at emit time and the exception detail was
  lost. All three now include a `%s` placeholder. Guarded by
  `GetSecretLogFormattingTests` (two tests) and
  `test_teams_not_configured_log_record_formats_cleanly`, which use the
  new `logging_enabled` / `assert_records_format_cleanly` helpers in
  `tests/_helpers.py` to capture and render the real `LogRecord`.

**Still latent (not fixed):**

_None currently tracked. See `get_forecast.py` line ~200 for remaining
`logger.debug("key=", value)` calls that will also raise at DEBUG level,
but those are gated off by the default log level so no runtime impact._
