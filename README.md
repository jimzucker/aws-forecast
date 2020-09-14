# aws-forecast

![Image of Cost Explorer](https://github.com/jimzucker/aws-forecast/blob/master/images/cost_explorer.png)

### User Story
I found myself logging in daily check our AWS spend and change to prior month to keep an eye on our AWS bill and decided to create a script to slack it one time per day to save time.

So I set out to automate this as a slack post daily to save time.  While doing this I found that the actual and forecast with % change from prior month that we see at the top of Cost Explorer are not directly available from the Cost Explorer API.  

### Acceptance Criteria
1. Numbers generated include percent change must be consistent with the numbers in Cost Explorer UI.
2. Application must produce a cleanly formatted one line output.
3. Code must be written as python functions that we can re-use to integrate into a slack-bot.
4. Post to slack if url is defined as an AWS secret (see below)
5. Provide example Lambda function that posts to slack on a cron 1 time per day

### Command line
```python3 get_forecast.py --profile <aws profile>  --type [FORECAST | ACTUALS]```

### Sample Output
![Sample Output of get_forecast](https://github.com/jimzucker/aws-forecast/blob/master/images/get_forecast_sample_output.png)

### Enabling Slack
To enable posting the message to Slack you must define a secret in secrets manager called 'awsgenie_secret_manager' with key=slack_url and value=<slack url>.

### Enabling SNS
To enable posting the message to SNS you must define a secret in secrets manager called 'awsgenie_secret_manager' with key=sns_arn and value=<sns arn>.

![Enabling Slack](https://github.com/jimzucker/aws-forecast/blob/master/images/aws_secret.png)

### Setting up Lambda
There are 3 parts to configuring this to run as a Lambda
1. IAM Role for Lambda - The IAM Role for you Lambda will have to give permissions for Lambda and Cost Explorer.
2. Trigger - Event Bridge(Cloudwatch Alarms) setup with a cron expression to trigger a run daily.
3. Function Code - You can directly paste in the get_forecast.py file is is all ready to go.

[Click here for instructions for setting up Lambda](https://github.com/jimzucker/aws-forecast/blob/master/LAMBDA_README.md)

# AWS Architecture
![AWS Architecture](https://github.com/jimzucker/aws-forecast/blob/master/images/aws_architecture.png)


# Technical Notes

#### SSL Errors posting message to slack
If you get SSL Cert errors defining this environment varialbe may help you:
```
export SSL_CERT_FILE=$(python -m certifi)
```

### AWS API Used
1. get_cost_forecast - used to get current month forecast. (note we exclude credits)
2. get_cost_and_usage - used to get prior & current month actuals (note we exclude credits)

### Boundary conditions handled
In testing I found several situations where the calls to get_cost_forecast would fail that we address in function calc_forecast:
1. Weekends - there is a sensitivity to the start date being on a weekend
2. Failure on new accounts or start of the month - on some days the calc fails due to insufficient data and we have to fall back to actuals

# Backlog
1. Deploy the whole thing as infrastructure as code with Cloud Formation

