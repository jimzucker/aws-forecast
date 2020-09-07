# Setting up Lambda
There are 3 parts to configuring this to run as a Lambda
1. IAM Role for Lambda - The IAM Role for you Lambda will have to give permissions for Lambda and Cost Explorer.
2. Trigger - Event Bridge(Cloudwatch Alarms) setup with a cron expression to trigger a run daily.
3. Function Code - You can directly paste in the get_forecast.py file is all ready to go.

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
