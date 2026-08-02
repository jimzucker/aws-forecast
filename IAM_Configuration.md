# IAM configuration for the GitHub → S3 upload workflow

`.github/workflows/s3-upload.yml` uploads `get_forecast.zip` to S3 on every
push to `main`. It authenticates with **GitHub OIDC federation** — the job
assumes an IAM role using a short-lived token issued by GitHub, so **no AWS
access keys are stored in the repository**.

One-time setup in the AWS account that owns the bucket:

## 1. Create the GitHub OIDC identity provider

IAM → Identity providers → Add provider:

- Provider type: **OpenID Connect**
- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

(Skip if the account already has this provider — an account can only have one.)

## 2. Create the deploy role

IAM → Roles → Create role → **Web identity**, choosing the provider above.
The trust policy should restrict the role to this repository's `main` branch:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    "token.actions.githubusercontent.com:sub": "repo:jimzucker/aws-forecast:ref:refs/heads/main"
                }
            }
        }
    ]
}
```

Attach an inline permissions policy scoped to the one object the workflow
writes:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "UploadLambdaZip",
            "Effect": "Allow",
            "Action": "s3:PutObject",
            "Resource": "arn:aws:s3:::jimzucker-github-getforecast/get_forecast.zip"
        }
    ]
}
```

## 3. Point the workflow at the role

Repository → Settings → Secrets and variables → Actions → New repository
secret:

- Name: `AWS_DEPLOY_ROLE_ARN`
- Value: the ARN of the role from step 2 (e.g.
  `arn:aws:iam::<ACCOUNT_ID>:role/github-aws-forecast-deploy`)

The old `AWS_ACCESS_KEY` / `AWS_SECRET_KEY` secrets are no longer used and
should be deleted, and the IAM user that owned those keys can be removed.

## Forking this repo?

Change `repo:jimzucker/aws-forecast` in the trust policy to your fork, and
point the workflow's `aws s3 cp` destination (and this policy's `Resource`)
at your own bucket.
