# aws-forecast

![Image of Cost Explorer](https://github.com/jimzucker/aws-forecast/blob/master/images/cost_explorer.png)

### User Story
I found myself logging in daily check our AWS spend and change to prior month to keep an eye on our AWS bill and decided to create a script to slack it one time per day to save time.

So I set out to automate this as a slack post daily to save time.  While doing this I found that the actual and forecast with % change from prior month that we see at the top of Cost Explorer are not directly available from the Cost Explorer API.  

### Acceptance Criteria
1. Numbers generated include percent change must be consistent with the numbers in Cost Explorer UI.
2. Application must produce a cleanly formatted one line output.
3. Code must be written as python functions that we can re-use to integrate into a slack-bot.

# Technical Notes

### Command line
```python3 get_forecast.py --profile <aws profile>  --type [FORECAST | ACTUALS]```

### Sample Output
![Sample Output of get_forecast](https://github.com/jimzucker/aws-forecast/blob/master/images/get_forecast_sample_output.png)

### AWS API Used
1. get_cost_forecast - used to get current month forecast. (note we exclude credits)
2. get_cost_and_usage - used to get prior & current month actuals (note we exclude credits)

### Boundary conditions handled
In testing I found several situations where the calls to get_cost_forecast would fail that we address in function calc_forecast:
1. Weekends - there is a sensitivity to the start date being on a weekend
2. Failure on new accounts or start of the month - on some days the calc fails due to insufficient data and we have to fall back to actuals

# Backlog
1. Add example Lambda function that posts to slack on a cron 1 time per day
2. Deploy the whole thing as infrastructure as code with Cloud Formation

