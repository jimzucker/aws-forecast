# aws-forecast

Reproduces the **forecast $** and **% change** numbers shown at the top of the AWS Cost Explorer UI (which the API does not expose directly) and posts them to Slack, Microsoft Teams, and/or SNS once a day.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

![Cost Explorer](https://github.com/jimzucker/aws-forecast/blob/main/images/cost_explorer.png)

## Contents

- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Skills (Claude / ChatGPT / Alexa)](#skills)
- [Development](#development)
- [License & disclaimer](#license--disclaimer)

## What it does

Once a day, calls AWS Cost Explorer for:

- Month-to-date spend (current month, all linked accounts)
- Forecasted total for the current month
- Percent change vs. the prior month

…then formats it as a fixed-width table and pushes it to whichever channels you've configured (Slack webhook, Teams webhook, SNS topic — all optional). Runs as both a Lambda function (scheduled) and a CLI tool (for testing).

Sample output:

![Sample Output](https://github.com/jimzucker/aws-forecast/blob/main/images/get_forecast_sample_output.png)

## Quick start

**Run the script locally** (requires AWS credentials with `ce:GetCostAndUsage`, `ce:GetCostForecast`, `organizations:DescribeAccount`, `sts:GetCallerIdentity`):

```bash
python3 get_forecast.py
```

For Lambda deployment, see [Deployment](#deployment).

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `GET_FORECAST_COLUMNS_DISPLAYED` | `"Account,Forecast,Change"` | Columns and order |
| `GET_FORECAST_ACCOUNT_COLUMN_WIDTH` | `12` | Max width for account name |
| `GET_FORECAST_AWS_PROFILE` | _(none)_ | Named AWS profile for CLI use |
| `AWS_LAMBDA_FUNCTION_NAME` | _(auto-set)_ | Presence signals Lambda context |

Slack/Teams/SNS destinations are read from a Secrets Manager entry named `awsgenie_secret_manager` whose value is JSON with keys `slack_url`, `teams_url`, `sns_arn` (any subset; missing keys disable that channel).

## Deployment

### CloudFormation

`get_forecast_cf.yaml` provisions Lambda + IAM + EventBridge + Secrets Manager. It loads code from the public bucket `s3://jimzucker-github-getforecast/get_forecast.zip`.

![CloudFormation Inputs](https://github.com/jimzucker/aws-forecast/blob/main/images/cloudformation_inputs.png)

For more, see [LAMBDA_README.md](LAMBDA_README.md). For manual setup (no CloudFormation), see [MANUAL_SETUP_README.md](MANUAL_SETUP_README.md).

### CI/CD: GitHub → S3

`.github/workflows/s3-upload.yml` zips and uploads on push to `main`. Requires repo secrets `AWS_ACCESS_KEY` / `AWS_SECRET_KEY`. IAM permission details: [IAM_Configuration.md](IAM_Configuration.md).

### AWS architecture

![AWS Architecture](https://github.com/jimzucker/aws-forecast/blob/main/images/aws_architecture.png)

## Skills

In addition to the daily Slack/Teams/SNS push, the same `calc_forecast()` engine powers three on-demand surfaces — each on its own branch with its own deploy artifacts and tests:

| Surface | Branch | How to ask |
|---|---|---|
| **Claude** (web/desktop via Custom Connector + a terminal-mode Claude Code skill) | [`claudeskill`](https://github.com/jimzucker/aws-forecast/tree/claudeskill) | "What's my AWS bill this month?" |
| **ChatGPT** (Custom GPT Action) | [`chatgptskill`](https://github.com/jimzucker/aws-forecast/tree/chatgptskill) | Same, in a Custom GPT |
| **Alexa** (custom skill) | [`alexaskill`](https://github.com/jimzucker/aws-forecast/tree/alexaskill) | "Alexa, ask AWS Cost what is my current bill" |

Each surface is independent — a separate Lambda + IAM role + (where applicable) bearer token in your own AWS account. Setup walkthroughs live in `CLAUDE_SKILL_README.md`, `CHATGPT_SKILL_README.md`, and `ALEXA_SKILL_README.md` on their respective branches.

## Development

- **Tests** — `pip install -r requirements-dev.txt && python3 -m unittest discover -v`. All AWS calls are mocked; no credentials needed. See [TESTING.md](TESTING.md).
- **Project guide for Claude Code** — [CLAUDE.md](CLAUDE.md).
- **AWS APIs used** — `get_cost_and_usage` (MTD + prior month) and `get_cost_forecast` (end-of-month projection). Both with `RECORD_TYPE != Credit/Refund` filter so credits don't distort the picture.
- **Edge cases handled in `calc_forecast`** — weekend forecast failures (CE is sensitive to weekend start dates); new accounts / start-of-month with insufficient history (falls back to MTD); missing Organizations access (falls back to raw account ID).

## License & disclaimer

Licensed under the [Apache License 2.0](LICENSE). Copyright © 2020 Jim Zucker.

**This is provided "as is", without warranty of any kind.** The forecast figures come from AWS Cost Explorer's own forecast model and can be wrong, especially early in the month or for accounts with sparse history. **Do not use this output as the sole basis for budget decisions, contractual commitments, or chargeback calculations** — verify against your AWS bill before acting on it. The author is not liable for any cost overruns, missed forecasts, or downstream consequences. See sections 7 and 8 of the LICENSE for the full disclaimer.
