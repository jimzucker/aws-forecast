# Enabling Slack
To enable posting the message to Slack you must define a secret in secrets manager called 'awsgenie_secret_manager' with key=slack_url and value=<slack url>.

# Enabling SNS
To enable posting the message to SNS you must define a secret in secrets manager called 'awsgenie_secret_manager' with key=sns_arn and value=<sns arn>.

# Enabling Teams
To enable posting the message to Teams you must define a secret in secrets manager called 'awsgenie_secret_manager' with key=teams_url and value=<teams url>.

![Enabling Slack](https://github.com/jimzucker/aws-forecast/blob/main/images/aws_secret.png)

# Setting up Lambda
There are 3 parts to configuring this to run as a Lambda
1. IAM Role for Lambda - The IAM Role for you Lambda will have to give permissions for Lambda and Cost Explorer.
2. Trigger - Event Bridge(Cloudwatch Alarms) setup with a cron expression to trigger a run daily.
3. Function Code - You can directly paste in the get_forecast.py file is is all ready to go.

[Click here for instructions for setting up Lambda](https://github.com/jimzucker/aws-forecast/blob/main/LAMBDA_README.md)

# Technical Notes

#### SSL Errors posting message to slack
If you get SSL Cert errors defining this environment varialbe may help you:
```
export SSL_CERT_FILE=$(python -m certifi)
```
