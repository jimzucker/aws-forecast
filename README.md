# aws-forecast

# AWS Architecture
![AWS Architecture](https://github.com/jimzucker/aws-forecast/blob/main/images/aws_architecture.png)

### Environment Variables
We use these to make it compatible with running the same script from Lambda and the commandline for testing

	GET_FORECAST_COLUMNS_DISPLAYED - specify columnns to display and the order 
	    default: "Account,MTD,Forecast,Change"

	GET_FORECAST_ACCOUNT_COLUMN_WIDTH - max width for account name for formatting
		default: 17

	AWS_LAMBDA_FUNCTION_NAME - set if running in lambda(Automatically set in Lambda)
	GET_FORECAST_AWS_PROFILE - set for testing on command line to pick a profile from your credentials file

### Cloud Formation
If you enter and slack URL and/or SNS it will publish in addition to logging.

#### File: get_forecast_cf.yaml
![Cloud Formation Inputs ](https://github.com/jimzucker/aws-forecast/blob/main/images/cloudformation_inputs.png)

	Note: The Cloud Formation loads the python script from a public S3 bucket, s3://jimzucker-github-getforecast/get_forecast.zip
	
### Sample Output
![Sample Output of get_forecast](https://github.com/jimzucker/aws-forecast/blob/main/images/get_forecast_sample_output.png)
	
### Command line (for development/testing)
```python3 get_forecast.py```

## User Story
I found myself logging in daily check our AWS spend and change to prior month to keep an eye on our AWS bill and decided to create a script to slack it one time per day to save time.

So I set out to automate this as a slack post daily to save time.  While doing this I found that the actual and forecast with % change from prior month that we see at the top of Cost Explorer are not directly available from the Cost Explorer API.  

![Image of Cost Explorer](https://github.com/jimzucker/aws-forecast/blob/main/images/cost_explorer.png)

## Acceptance Criteria
1. Numbers generated include percent change must be consistent with the numbers in Cost Explorer UI.
2. Application must produce a cleanly formatted one line output.
3. Code must be written as python functions that we can re-use to integrate into a slack-bot.
4. Post to slack if url is defined as an AWS secret (see below)
5. Provide example Lambda function that posts to slack on a cron 1 time per day

### Technical Notes

#### AWS API Used
1. get_cost_forecast - used to get current month forecast. (note we exclude credits)
2. get_cost_and_usage - used to get prior & current month actuals (note we exclude credits)

#### Boundary conditions handled
In testing I found several situations where the calls to get_cost_forecast would fail that we address in function calc_forecast:
1. Weekends - there is a sensitivity to the start date being on a weekend
2. Failure on new accounts or start of the month - on some days the calc fails due to insufficient data and we have to fall back to actuals


##	## Manual instructions
If you dont want to use the Cloud Formation document, see these instructions: [Click here](https://github.com/jimzucker/aws-forecast/blob/main/MANUAL_SETUP_README.md)
