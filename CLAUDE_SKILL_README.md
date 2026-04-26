# Claude Skill — AWS Cost Summary

A Claude skill that asks AWS Cost Explorer "what is my current spend / forecast / top account?" and answers in chat. Two delivery modes:

1. **Hosted connector** — A Lambda Function URL in your AWS account, gated by a bearer token, that Claude (web/desktop/mobile) calls via a Custom Connector. The user types nothing more than a single bearer token into the Claude UI.
2. **Terminal skill** — A `.claude/skills/aws-cost-summary/` directory consumed by Claude Code on the command line, using the user's local AWS profile. Read-only by construction (deny rules in `.claude/settings.json`).

## Architecture

```
   Claude.ai web/app                           Claude Code (terminal)
        │                                            │
   Bearer token in connector UI               ~/.aws/credentials profile
        │                                            │
        ▼                                            ▼
   Lambda Function URL                       python3 get_forecast.py
   (claude_connector_handler.py)             (.claude/skills/aws-cost-summary/run.sh)
        │                                            │
        └──────────► calc_forecast() ◄───────────────┘
                          │
                          ▼
                AWS Cost Explorer + Organizations
```

## Prerequisites

- An AWS account with permissions to deploy CloudFormation containing `Lambda`, `IAM::Role`, `SecretsManager::Secret`, `Lambda::Url`.
- AWS CLI v2 configured locally (`aws configure --profile <admin>`). Every `aws` command below should be run with `--profile <admin> --region <your-region>`.
- An S3 bucket in the same region for the Lambda zip — passed as `LAMBDA_BUCKET` env var.
- Python 3.12 + `pip` to build the zip.

## Hosted connector — deploy & install

### 1. Build the Lambda zip

```bash
export LAMBDA_BUCKET=my-lambda-code-bucket
export AWS_PROFILE=my-admin
export AWS_REGION=us-east-1
./build_claude.sh
```

This vendors `python-dateutil`, packages `get_forecast.py` + `claude_connector_handler.py`, and uploads to `s3://$LAMBDA_BUCKET/claude_connector.zip`.

### 2. Generate a bearer token and deploy

```bash
TOKEN=$(openssl rand -hex 32)
aws cloudformation deploy \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --template-file claude_connector_cf.yaml \
  --stack-name aws-cost-claude \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides BearerToken="$TOKEN" CodeS3Bucket="$LAMBDA_BUCKET"
```

### 3. Read the Function URL

```bash
aws cloudformation describe-stacks \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --stack-name aws-cost-claude \
  --query "Stacks[0].Outputs" --output table
```

### 4. (Optional) Re-read the bearer token later

```bash
aws secretsmanager get-secret-value \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --secret-id aws_cost_claude_connector \
  --query SecretString --output text | python3 -c 'import json,sys; print(json.load(sys.stdin)["claude_bearer_token"])'
```

### 5. Register the connector in Claude

In Claude (web or desktop) → Settings → Connectors / Custom Connectors → Add:

- Endpoint: the `FunctionUrl` from step 3.
- Authentication: Bearer token.
- Token: the value from step 2 (or step 4).
- Schema: paste the contents of `claude_connector_openapi.yaml` (after replacing `servers[0].url` with the Function URL).

### 6. Use it

In Claude, ask:

- "What's my AWS bill this month?"
- "How much am I forecasted to spend?"
- "Which AWS account is costing the most?"

Claude calls the connector with the bearer token, gets back JSON, and summarizes.

### 7. Update the Lambda after a code change

```bash
./build_claude.sh
aws lambda update-function-code \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --function-name aws-cost-claude-connector \
  --s3-bucket "$LAMBDA_BUCKET" --s3-key claude_connector.zip
```

### 8. Uninstall

```bash
aws cloudformation delete-stack \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --stack-name aws-cost-claude
```

This removes the Lambda, IAM role, Function URL, and Secrets Manager entry. Then remove the connector in the Claude UI.

## Terminal skill — install & use

For Claude Code in a terminal:

1. **Create an IAM user** (or reuse an existing role) with **only** these four read-only actions. Anything else widens the blast radius unnecessarily — the skill needs no write or list-all permissions:

   - `ce:GetCostAndUsage` — month-to-date and prior-month spend
   - `ce:GetCostForecast` — current-month forecast
   - `organizations:DescribeAccount` — resolves linked-account IDs to friendly names. **Optional:** if you skip this, account names display as 12-digit IDs (e.g. `760967184165`) instead of names like `prod-billing` — everything else still works.
   - `sts:GetCallerIdentity` — used for connection sanity checks

   Copy this JSON into a new IAM customer-managed policy (e.g. `aws-cost-readonly-claude`) and attach it to the user:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "ReadCostExplorer",
         "Effect": "Allow",
         "Action": [
           "ce:GetCostAndUsage",
           "ce:GetCostForecast"
         ],
         "Resource": "*"
       },
       {
         "Sid": "ResolveAccountNames",
         "Effect": "Allow",
         "Action": "organizations:DescribeAccount",
         "Resource": "*"
       },
       {
         "Sid": "WhoAmI",
         "Effect": "Allow",
         "Action": "sts:GetCallerIdentity",
         "Resource": "*"
       }
     ]
   }
   ```

   Cost Explorer and Organizations APIs do not support resource-level permissions, so `Resource: "*"` is the only valid form for these actions.

2. **Configure the profile locally** with the user's access key:

   ```bash
   aws configure --profile aws-cost-readonly
   ```

   You can press Enter on the region prompt — `run.sh` defaults to `us-east-1` if the profile has no region set.

3. (Optional) override the profile name:

   ```bash
   export AWS_COST_PROFILE=my-other-profile
   ```

4. The skill is auto-discovered from `.claude/skills/aws-cost-summary/` when Claude Code is started in this repo. To use system-wide, copy:

   ```bash
   mkdir -p ~/.claude/skills && cp -r .claude/skills/aws-cost-summary ~/.claude/skills/
   ```

5. In Claude Code, ask a cost question — Claude will run `bash .claude/skills/aws-cost-summary/run.sh` and read the table. On the first run the script auto-creates `<repo>/.venv-skill/` and installs `boto3` + `python-dateutil` (PEP 668 blocks pip on system Python). Subsequent runs reuse the venv.

The bundled `.claude/settings.json` denies AWS mutations (IAM, S3 delete, EC2 terminate, Lambda update, CFN deploy/delete, Secrets Manager mutations) for the duration of the session, so the skill cannot be coerced into a destructive action.

## Troubleshooting

| Symptom                                              | Cause / fix                                                                 |
|------------------------------------------------------|-----------------------------------------------------------------------------|
| Connector returns 401                                | Wrong bearer token. Re-fetch with step 4 above.                             |
| Connector returns 500 with "Cost Explorer unavailable" | Lambda IAM role lacks `ce:GetCostAndUsage` / `ce:GetCostForecast`.        |
| Connector returns 500 with "Auth backend unavailable"  | Lambda role lacks `secretsmanager:GetSecretValue`. Check CF deployed cleanly. |
| Terminal skill: `Unable to locate credentials`       | `aws-cost-readonly` profile doesn't exist. Run `aws configure --profile aws-cost-readonly`. |
| Terminal skill: account names display as 12-digit IDs | IAM principal lacks `organizations:DescribeAccount`. This is non-fatal — IDs are shown as fallback. |

## Test suite

All tests run offline (no AWS creds, no network). From the repo root:

```bash
python3 -m unittest discover -v
# or
pytest -q
```

Tests added for this skill:

- `tests/test_claude_connector_handler.py` — handler success/failure paths, auth, JSON shape, secret rotation.
- `tests/test_claude_connector_openapi.py` — OpenAPI parses, schema validates a sample response.
- `tests/test_claude_skill.py` — `run.sh` is executable + valid bash + execs `python3 get_forecast.py`; `SKILL.md` frontmatter; `.claude/settings.json` shape.
- `tests/test_claude_cf.py` — `claude_connector_cf.yaml` declares Lambda + Function URL + IAM role + secret with no wildcard IAM actions.
- `tests/test_messaging.py` — *expanded* with unicode, triple-backtick payloads, large bodies, JSON content-type assertions.
