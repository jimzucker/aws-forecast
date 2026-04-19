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

46 tests total.

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
| `calc_forecast`     | single-account totals, zero prior month → sentinel 100, prior-month lookup failure, forecast failure → fallback to usage, multi-page pagination |
| `publish_forecast`  | default columns, custom column env var, single-column env, message order follows forecast desc |
| `lambda_handler`    | delegates to `publish_forecast`, wraps errors in a generic exception |
| `main`              | exits 0 on success, uses `GET_FORECAST_AWS_PROFILE`, exits 1 on failure |

## Notes on bugs exposed by the suite

While writing these tests a few latent issues surfaced in `get_forecast.py`.
They're intentionally left unfixed (source wasn't changed) but are worth
flagging:

1. **Line 76 logger call** — `logger.error("...", e)` has no `%s` placeholder,
   so the logging module raises a `TypeError` during formatting. The suite
   suppresses this noise via `logging.disable`.
2. **Line 314 bare name** — `except AWSOrganizationsNotInUseException` refers
   to a symbol that is never imported. If `org.describe_account` raises, the
   handler itself will crash with `NameError`. The happy-path tests stub
   `describe_account` to succeed and avoid this landmine.
3. **`account_width` coercion** — `publish_forecast` reads
   `GET_FORECAST_ACCOUNT_COLUMN_WIDTH` as a string but passes it straight to
   `str.ljust`, which requires an int. The suite only exercises the
   default-int path.
