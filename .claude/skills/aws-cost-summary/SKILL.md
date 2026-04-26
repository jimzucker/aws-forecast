---
name: aws-cost-summary
description: Use when the user asks about current AWS spend, monthly forecast, or which AWS account is costing the most. Runs the read-only get_forecast.py tool against a configured AWS profile and posts the table to Slack/Teams if those URLs are in Secrets Manager.
---

# AWS Cost Summary

This skill fetches a month-to-date + forecast summary of AWS spend for the
configured account. It is **read-only** — it only calls Cost Explorer,
Organizations, and STS APIs. The accompanying `.claude/settings.json` denies
mutating AWS commands while the skill is active.

## When to invoke

The user asks something like:
- "What's my AWS bill this month?"
- "How much am I forecasted to spend?"
- "Which AWS account is costing the most?"
- "What's the cost change from last month?"

## How to invoke

Run the wrapper script and then summarize the table that comes back on stdout:

```bash
bash .claude/skills/aws-cost-summary/run.sh
```

The script:
1. Sets `GET_FORECAST_AWS_PROFILE` from `${AWS_COST_PROFILE:-aws-cost-readonly}`.
2. Execs `python3 get_forecast.py`.

The output is a fixed-width table with columns Account, MTD, Forecast, Change.
Read the largest forecast row(s) and answer the user's question directly with
those numbers.

## One-time setup the user must do

1. Create an AWS IAM user or role with **read-only** permissions on Cost
   Explorer + Organizations:
   - `ce:GetCostAndUsage`
   - `ce:GetCostForecast`
   - `organizations:DescribeAccount`
   - `sts:GetCallerIdentity`
2. Configure it as a named profile:
   ```
   aws configure --profile aws-cost-readonly
   ```
3. (Optional) override the profile name with `export AWS_COST_PROFILE=<name>`.

The skill remembers the **profile name**, never the credentials. Credentials
live in `~/.aws/credentials` under standard AWS tooling.

## Notes for Claude

- If `run.sh` exits non-zero, do not retry by altering the script. Surface the
  error to the user — usually it means the AWS profile is missing or has
  insufficient permissions.
- Do not invoke any other AWS CLI commands while answering. The skill is
  intentionally scoped to this one read-only call.
