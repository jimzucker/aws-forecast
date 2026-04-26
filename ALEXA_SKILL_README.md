# Alexa Skill — AWS Cost Summary

An Alexa skill that answers "what is my current AWS bill" with month-to-date spend, current-month forecast, and percent change versus last month. The skill runs as a Lambda in your own AWS account; no per-user credentials flow through Alexa — it's authenticated by the Alexa Skills Kit principal bound to your skill ID.

## Architecture

```
   Alexa-enabled device
        │
   "Alexa, ask AWS Cost what is my current bill"
        │
        ▼
   Alexa Skills Kit (alexa-appkit.amazon.com principal)
        │
        ▼
   Lambda (alexa_handler.py)
        │
        ▼
   calc_forecast()  ─────►  AWS Cost Explorer + Organizations
        │
        ▼
   SSML response: "Your AWS month-to-date spend is $X..."
```

## Prerequisites

- An AWS account with permissions to deploy CloudFormation containing `Lambda`, `IAM::Role`, `Lambda::Permission`.
- AWS CLI v2 configured locally (`aws configure --profile <admin>`). All `aws` commands use `--profile <admin> --region <your-region>`.
- An S3 bucket in the same region for the Lambda zip — passed as `LAMBDA_BUCKET` env var.
- Python 3.12 + `pip` to build the zip.
- A free **Amazon Developer** account at developer.amazon.com (separate from your AWS account).

## Deploy & install

### 1. Create the Alexa skill (no code yet)

In developer.amazon.com → Alexa → Alexa Skills Kit → Create Skill:

- Skill name: **AWS Cost** (or anything you like — note this becomes the invocation prefix).
- Primary locale: your language.
- Choose a model to add to your skill: **Custom**.
- Choose a method to host your skill's backend resources: **Provision your own**.
- Click Create Skill, then on the template chooser pick **Start from Scratch** (no template).

After creation, copy the **Skill ID** from the developer console — it looks like `amzn1.ask.skill.<uuid>` and you'll need it in step 3.

### 2. Build the Lambda zip

```bash
export LAMBDA_BUCKET=my-lambda-code-bucket
export AWS_PROFILE=my-admin
export AWS_REGION=us-east-1
./build_alexa.sh
```

### 3. Deploy the CloudFormation stack

```bash
aws cloudformation deploy \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --template-file alexa_skill_cf.yaml \
  --stack-name aws-cost-alexa \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    AlexaSkillId=amzn1.ask.skill.YOUR-UUID-HERE \
    CodeS3Bucket="$LAMBDA_BUCKET"
```

The `EventSourceToken: !Ref AlexaSkillId` in the template restricts invocation to *your* skill ID — no other Alexa skill can call this Lambda.

### 4. Get the Lambda ARN

```bash
LAMBDA_ARN=$(aws cloudformation describe-stacks \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --stack-name aws-cost-alexa \
  --query "Stacks[0].Outputs[?OutputKey=='LambdaArn'].OutputValue" \
  --output text)
echo "$LAMBDA_ARN"
```

### 5. Wire Alexa → Lambda

Back in the Alexa developer console for your skill:

1. Endpoint (left nav) → AWS Lambda ARN → Default Region → paste `$LAMBDA_ARN`.
2. Save Endpoints.

### 6. Upload the interaction model

In the Alexa developer console:

1. Build (top tab) → Interaction Model → JSON Editor (left nav).
2. Replace the contents with `alexa/interaction_model.json` from this repo.
3. Save Model.
4. Build Model (button at the top). Wait for the build to succeed.

### 7. Test

In the Alexa developer console → Test (top tab):

- Set the dropdown from "Off" to "Development".
- Type or say: **"ask AWS Cost what is my current bill"**.
- You should hear/see SSML like *"Your AWS month-to-date spend is $123. The forecast for this month is $456, a 78 percent change from last month."*

On a real Echo logged into the same Amazon account:

> "Alexa, ask AWS Cost what is my current bill."

### 8. Update the Lambda after a code change

```bash
./build_alexa.sh
aws lambda update-function-code \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --function-name aws-cost-alexa-handler \
  --s3-bucket "$LAMBDA_BUCKET" --s3-key alexa_handler.zip
```

If you change the interaction model, re-upload via the Alexa developer console (step 6).

### 9. Uninstall

```bash
aws cloudformation delete-stack \
  --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --stack-name aws-cost-alexa
```

Then delete the skill in the Alexa developer console (Skills list → your skill → ⋮ → Delete Skill).

## Troubleshooting

| Symptom                                                | Cause / fix                                                                |
|--------------------------------------------------------|----------------------------------------------------------------------------|
| Test tab returns "There was a problem with the requested skill's response" | Lambda returned a non-SSML envelope. Check CloudWatch logs at `/aws/lambda/aws-cost-alexa-handler`. |
| Skill says "I couldn't reach Cost Explorer right now"  | Lambda IAM role missing `ce:GetCostAndUsage` / `ce:GetCostForecast`. Check CF deployed cleanly. |
| Skill says "I didn't understand"                       | Interaction model not built or invocation name mismatch. Re-do step 6 and re-build the model. |
| Alexa device responds "I'm sorry, I'm not able to help you with that" | The skill isn't enabled for the Amazon account paired with the Echo. In the Alexa app, enable your skill in dev mode. |
| `aws cloudformation deploy` fails with `EventSourceToken` error | The skill ID format is wrong. It must start with `amzn1.ask.skill.`. |

## Test suite

All tests run offline (no AWS creds, no network). From the repo root:

```bash
python3 -m unittest discover -v
# or
pytest -q
```

Tests added for this skill:

- `tests/test_alexa_handler.py` — every dispatch path (LaunchRequest, WhatIsMyBillIntent, Help/Cancel/Stop/Fallback, SessionEndedRequest, unknown intent), graceful-failure SSML when `calc_forecast` raises, response envelope shape per Alexa schema, SSML well-formedness.
- `tests/test_alexa_interaction_model.py` — invocation name, required intents present, every intent has at least one sample utterance.
- `tests/test_alexa_cf.py` — `alexa_skill_cf.yaml` declares Lambda + IAM role + ASK Lambda::Permission with the correct principal and skill-id binding, no wildcard IAM actions.
