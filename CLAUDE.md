# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Single-file Python tool (`get_forecast.py`) that reproduces AWS Cost Explorer UI forecast/percent-change metrics (not directly available from the API) and posts daily cost reports to Slack, Microsoft Teams, and/or SNS. Runs as both an AWS Lambda function and a CLI tool.

## Commands

```bash
# Run tests (no AWS credentials needed — all AWS calls are mocked).
# Requires python-dateutil at minimum; install dev deps for the full toolchain.
pip install -r requirements-dev.txt
python3 -m unittest discover -v
pytest
pytest tests/test_calc_forecast.py      # single module
pytest -k test_single_account           # single test by name

# Run the script locally (requires real AWS credentials)
python3 get_forecast.py

# Build and upload Lambda zip to S3
./build.sh
```

## Architecture

All logic lives in `get_forecast.py`. Call chain:

```
lambda_handler() / main()
  └─ publish_forecast(boto3_session)      # reads env vars, assembles table message
       ├─ calc_forecast(boto3_session)    # Cost Explorer API calls, math, account names
       ├─ format_rows(output, width)      # sorts, formats currency/%, builds header
       └─ display_output(session, msg)    # dispatches to channels
            ├─ get_secret(sm_client)      # Secrets Manager → JSON with URLs/ARN
            ├─ send_slack(url, msg)
            ├─ send_teams(url, msg)
            └─ send_sns(session, arn, msg)
```

**Key design points:**
- `lambda_handler` and `main()` both call `publish_forecast` — same code path for Lambda and CLI.
- `calc_forecast` handles several fallback cases: weekend forecast failures, new accounts with insufficient history, and missing AWS Organizations access all fall back to current-month actuals or account ID.
- Prior-month variance of 0 uses sentinel value `100` (→ displayed as "NEW").
- Secret key in Secrets Manager is hardcoded: `awsgenie_secret_manager`.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `GET_FORECAST_COLUMNS_DISPLAYED` | `"Account,Forecast,Change"` | Columns to display and order |
| `GET_FORECAST_ACCOUNT_COLUMN_WIDTH` | `12` | Max width for account name column |
| `GET_FORECAST_AWS_PROFILE` | _(none)_ | Named AWS profile for CLI use |
| `AWS_LAMBDA_FUNCTION_NAME` | _(auto-set by Lambda)_ | Presence signals Lambda context |

## Test Infrastructure

Tests in `tests/` use `unittest.mock` — no real AWS calls, no credentials needed.

- `tests/__init__.py` — stubs boto3/botocore if not installed; disables logger output. Does **not** stub `python-dateutil`, which `get_forecast.py` imports at module load — install it before running the suite.
- `tests/_helpers.py` — shared mock factories (`make_mock_boto3_session`, `usage_response`, `grouped_usage_response`, `forecast_response`, `logging_enabled`)

Skill branches (`claudeskill`, `chatgptskill`, `alexaskill`) add tests that `import yaml`; install `pyyaml` (already pinned in `requirements-dev.txt`) before running their suites.

The `logging_enabled()` context manager in `_helpers.py` is used to assert log output; use it when testing error/warning log paths.

## Deployment

- **CloudFormation**: `get_forecast_cf.yaml` provisions Lambda + IAM + EventBridge + Secrets Manager. Loads code from public S3: `s3://jimzucker-github-getforecast/get_forecast.zip`.
- **CI/CD**: `.github/workflows/s3-upload.yml` zips and uploads on push to `main`. Authenticates via GitHub OIDC federation (role ARN in the `AWS_DEPLOY_ROLE_ARN` repo secret); setup in `IAM_Configuration.md`.
- **Lambda runtime**: Python 3.13. Only non-stdlib runtime dependency is `python-dateutil` (for `relativedelta`).
