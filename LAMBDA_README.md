# Setting up Lambda
There are 3 parts to configuring this to run as a Lambda
1. IAM Role for Lambda - The IAM Role for you Lambda will have to give permissions for Lambda and Cost Explorer.
2. Trigger - Event Bridge(Cloudwatch Alarms) setup with a cron expression to trigger a run daily.
3. Function Code - You can directly paste in the get_forecast.py file is all ready to go.

## Configuring Slack 7 Secrets (From AWS Blueprint "cloudwatch-alarm-to-slack-python")
### Follow these steps to configure the webhook in Slack

  1. Navigate to https://<your-team-domain>.slack.com/services/new

  2. Search for and select "Incoming WebHooks".

  3. Choose the default channel where messages will be sent and click "Add Incoming WebHooks Integration".

  4. Copy the webhook URL from the setup instructions and use it in the next section.

### To encrypt your secrets use the following steps
(*TODO: currently not supported you must use secrets manager)
  1. Create or use an existing KMS Key - http://docs.aws.amazon.com/kms/latest/developerguide/create-keys.html

  2. Expand "Encryption configuration" and click the "Enable helpers for encryption in transit" checkbox

  3. Paste <SLACK_CHANNEL> into the slackChannel environment variable

  Note: The Slack channel does not contain private info, so do NOT click encrypt

  4. Paste <SLACK_HOOK_URL> into the kmsEncryptedHookUrl environment variable and click "Encrypt"

  Note: You must exclude the protocol from the URL (e.g. "hooks.slack.com/services/abc123").

  5. Give your function's role permission for the `kms:Decrypt` action using the provided policy template


## IAM Role
When you create the Lambda it will create a role for you with required Lambda permissions, you must add the following
 permissions to it:
![Lambda IAM Role](https://github.com/jimzucker/aws-forecast/blob/master/images/IAM_permissions.png)

## Configuring Trigger
Here is an example trigger, keep in mind the cron runs in UTC Timezone.
![Lambda Trigger](https://github.com/jimzucker/aws-forecast/blob/master/images/event_bridge.png)

## Function Code
You can directly copy and paste get_forecast.py into the Lambda definition without modifications.
![Lambda Function Code](https://github.com/jimzucker/aws-forecast/blob/master/images/lambda_function.png)

# AWS Architecture
![AWS Architecture](https://github.com/jimzucker/aws-forecast/blob/master/images/aws_architecture.png)
