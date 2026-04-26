# ChatGPT Skill — AWS Cost Summary

A Custom GPT Action that asks AWS Cost Explorer "what is my current spend / forecast / top account?" and answers in chat.openai.com. The user pastes one bearer token into the GPT builder; AWS credentials live in an IAM role attached to the Lambda in their own AWS account.

## Architecture

```
   ChatGPT app (Custom GPT)
        │
   Bearer token in GPT auth UI ──► Authorization: Bearer <token>
        │
        ▼
   Lambda Function URL
   (chatgpt_action_handler.py)
        │
        ▼
   calc_forecast()
        │
        ▼
   AWS Cost Explorer + Organizations
```

## Prerequisites

- An AWS account with permissions to deploy CloudFormation containing `Lambda`, `IAM::Role`, `SecretsManager::Secret`, `Lambda::Url`.
- AWS CLI v2 configured locally (`aws configure --profile <admin>`). All `aws` commands use `--profile <admin> --region <your-region>`.
- An S3 bucket in the same region for the Lambda zip — passed as `LAMBDA_BUCKET` env var.
- Python 3.12 + `pip` to build the zip.
- A **ChatGPT Plus, Team, or Enterprise** subscription (Custom GPT creation is gated to paid tiers).

## Deploy & install

### 1. Build the Lambda zip

```bash
export LAMBDA_BUCKET=my-lambda-code-bucket
export AWS_PROFILE=my-admin
export AWS_REGION=us-east-1
./build_chatgpt.sh
```

This vendors `python-dateutil`, packages `get_forecast.py` + `chatgpt_action_handler.py`, and uploads to `s3://$LAMBDA_BUCKET/chatgpt_action.zip`.

### 2. Generate a bearer token and deploy

```bash
TOKEN=$(openssl rand -hex 32)
aws cloudformation deploy \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --template-file chatgpt_action_cf.yaml \
  --stack-name aws-cost-chatgpt \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides BearerToken="$TOKEN" CodeS3Bucket="$LAMBDA_BUCKET"

# Save the token — you'll need it in the GPT builder.
echo "$TOKEN"
```

### 3. Get the Function URL

```bash
FN_URL=$(aws cloudformation describe-stacks \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --stack-name aws-cost-chatgpt \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionUrl'].OutputValue" \
  --output text)
echo "$FN_URL"
```

### 4. Patch the OpenAPI spec with the Function URL

```bash
sed "s#https://REPLACE_ME.lambda-url.REGION.on.aws#${FN_URL%/}#" \
  chatgpt_action_openapi.yaml > /tmp/chatgpt_action_openapi.yaml
cat /tmp/chatgpt_action_openapi.yaml
```

(Or do it manually in the GPT builder — replace `servers[0].url` with the Function URL.)

### 5. Create the Custom GPT

In chat.openai.com:

1. Sidebar → Explore GPTs → Create.
2. Configure tab → Actions → Create new action.
3. Schema → paste the contents of `/tmp/chatgpt_action_openapi.yaml` from step 4.
4. Authentication → API Key → Auth Type: **Bearer** → paste the token from step 2.
5. Save the GPT (Update / Save in top right).

### 6. Use it

Open the new GPT and ask:

- "What's my AWS bill this month?"
- "Forecast my AWS spend."
- "Which AWS account is using the most money?"

ChatGPT calls the Lambda via the bearer token, gets back the JSON, and summarizes.

### 7. Update the Lambda after a code change

```bash
./build_chatgpt.sh
aws lambda update-function-code \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --function-name aws-cost-chatgpt-action \
  --s3-bucket "$LAMBDA_BUCKET" --s3-key chatgpt_action.zip
```

### 8. Rotate the bearer token

```bash
NEW_TOKEN=$(openssl rand -hex 32)
aws secretsmanager put-secret-value \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --secret-id aws_cost_chatgpt_action \
  --secret-string "{\"chatgpt_bearer_token\": \"$NEW_TOKEN\"}"
```

Then update the API Key in the GPT builder with `$NEW_TOKEN`. The handler does not cache the secret so the change is immediate.

### 9. Uninstall

```bash
aws cloudformation delete-stack \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --stack-name aws-cost-chatgpt
```

Then delete the Custom GPT in chat.openai.com (GPT page → Edit → ⋯ → Delete).

## Troubleshooting

| Symptom                                                | Cause / fix                                                                |
|--------------------------------------------------------|----------------------------------------------------------------------------|
| GPT builder rejects schema with "missing servers"      | The `servers[0].url` placeholder is still in the YAML. Re-run step 4.      |
| Action returns 401                                     | Token mismatch. Re-paste the token from step 2 into the GPT builder.      |
| Action returns 500 with "Cost Explorer unavailable"    | Lambda IAM role missing CE permissions. Confirm CF deployed cleanly.      |
| Action returns 500 with "Auth backend unavailable"     | Lambda role missing `secretsmanager:GetSecretValue`. Same fix.            |
| GPT says "Action returned an unexpected response"      | The Function URL is wrong — verify the URL Path is `/`, not `/cost`.      |

## Test suite

All tests run offline (no AWS creds, no network). From the repo root:

```bash
python3 -m unittest discover -v
# or
pytest -q
```

Tests added for this skill:

- `tests/test_chatgpt_action_handler.py` — handler success/failure paths, auth, JSON shape, secret rotation.
- `tests/test_chatgpt_action_openapi.py` — OpenAPI parses, satisfies ChatGPT-specific constraints (`servers`, unique `operationId`, ≤30 ops, bearerAuth), schema validates a sample response.
- `tests/test_chatgpt_cf.py` — `chatgpt_action_cf.yaml` declares Lambda + Function URL + IAM role + secret with no wildcard IAM actions.
