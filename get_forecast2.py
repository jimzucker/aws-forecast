import argparse
import boto3
import datetime
from dateutil.relativedelta import relativedelta
import os

def calc_forecast(boto3_session):
    #create the clients we need for ce & org
    ce = session.client('ce')
    org = session.client('organizations')

    #initialize the standard filter
    not_filter= {
        "Not": {
            "Dimensions": {
                "Key": "RECORD_TYPE",
                "Values": [ "Credit", "Refund" ]
            }
        }
    }

    #get accountname for organization
    org_account_id = session.client('sts').get_caller_identity().get('Account')
    org_name=org.describe_account(AccountId=org_account_id)['Account']['Name']

    #Get total cost_and_usage
    results = []
    data = ce.get_cost_and_usage(
        TimePeriod={'Start': first_day_of_month, 'End':  first_day_next_month}
        , Granularity='MONTHLY', Metrics=['UnblendedCost'], Filter=not_filter
        )
    results = data['ResultsByTime']
    amount_usage = float(results[0]['Total']['UnblendedCost']['Amount'])

    try:
        data = ce.get_cost_and_usage(
            TimePeriod={'Start': first_day_prior_month, 'End':  first_day_of_month}
            , Granularity='MONTHLY', Metrics=['UnblendedCost'], Filter=not_filter
            )
        results = data['ResultsByTime']
        amount_usage_prior_month = float(results[0]['Total']['UnblendedCost']['Amount'])
    except Exception as e:
        amount_usage_prior_month = 0

    #Total Forecast
    try:
        data = ce.get_cost_forecast(
            TimePeriod={'Start': today, 'End':  first_day_next_month}
            , Granularity='MONTHLY', Metric='UNBLENDED_COST', Filter=not_filter
            )
        amount_forecast = float(data['Total']['Amount'])
    except Exception as e:
        amount_forecast = amount_usage

    forecast_variance = 100
    if amount_usage_prior_month > 0 :
        forecast_variance = (amount_forecast-amount_usage_prior_month) / amount_usage_prior_month *100

    result = {
        "account_name": 'Total',
        "amount_usage": amount_usage,
        "amount_forecast": amount_forecast,
        "forecast_variance": (amount_forecast-amount_usage_prior_month) / amount_usage_prior_month *100
    }
    output=[]
    output.append(result)

    #Get usage caose for all accounts
    results = []
    next_page_token = None
    while True:
        if next_page_token:
            kwargs = {'NextPageToken': next_page_token}
        else:
            kwargs = {}
        data = ce.get_cost_and_usage(
            TimePeriod={'Start': first_day_of_month, 'End':  first_day_next_month}
            , Granularity='MONTHLY', Metrics=['UnblendedCost'], Filter=not_filter
            , GroupBy=[{'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'}]
            , **kwargs)
        results += data['ResultsByTime']
        next_page_token = data.get('NextPageToken')
        if not next_page_token:
            break

    # Print each account
    for result_by_time in results:
        for group in result_by_time['Groups']:
            amount_usage = float(group['Metrics']['UnblendedCost']['Amount'])
            linked_account = group['Keys'][0]
            
            #create filter
            linked_account_filter = {
                "And": [
                    {
                      "Dimensions": {
                        "Key": "LINKED_ACCOUNT",
                        "Values": [
                          linked_account
                        ]
                      }
                    },
                    not_filter
                ]
            }
            
            #get prior-month usage, it may not exist
            try:
                data = ce.get_cost_and_usage(
                    TimePeriod={'Start': first_day_prior_month, 'End':  first_day_of_month}
                    , Granularity='MONTHLY', Metrics=['UnblendedCost'], Filter=linked_account_filter
                    )
                results = data['ResultsByTime']
                amount_usage_prior_month = float(results[0]['Total']['UnblendedCost']['Amount']) 
            except Exception as e:
                amount_usage_prior_month = 0

            #Forecast, there maybe insuffcient data on a new account
            try:
                data = ce.get_cost_forecast(
                    TimePeriod={'Start': today, 'End':  first_day_next_month}
                    , Granularity='MONTHLY', Metric='UNBLENDED_COST', Filter=linked_account_filter
                    )
                amount_forecast = float(data['Total']['Amount'])
            except Exception as e:
                amount_forecast = amount_usage

            variance = 100
            if amount_usage_prior_month > 0 :
                variance = (amount_forecast-amount_usage_prior_month) / amount_usage_prior_month *100

            account_name=org.describe_account(AccountId=linked_account)['Account']['Name']
            result = {
                "account_name": account_name,
                "amount_usage": amount_usage,
                "amount_forecast": amount_forecast,
                "forecast_variance": variance
            }
            output.append(result)
    return output


def format_rows(output,account_width):
    #print the heading
    mtd_width=8
    forecast_width=9
    change_width=7

    output_rows=[]

    row = {
        "Account": 'Account'.ljust(account_width),
        "MTD": 'MTD'.rjust(mtd_width),
        "Forecast": 'Forecast'.rjust(forecast_width),
        "Change": 'Change'.rjust(change_width)
    }
    output_rows.append(row)

    #print in decending order by forecast
    lines = sorted(output, key=lambda k: k.get('amount_forecast'), reverse=True)
    for line in lines :
        if len(lines) == 2 and line.get('account_name') == 'Total':
            break
        change = "{0:,.1f}%".format(line.get('forecast_variance'))
        row = {
            "Account": line.get('account_name')[:account_width].ljust(account_width),
            "MTD": "${0:,.0f}".format(line.get('amount_usage')).rjust(mtd_width),
            "Forecast": "${0:,.0f}".format(line.get('amount_forecast')).rjust(forecast_width),
            "Change": change.rjust(change_width)
        }
        output_rows.append(row)

    return output_rows

#read params
enable_debug=""
if 'GET_FORECAST_ENABLE_DEBUG' in os.environ:
    enable_debug=os.environ['GET_FORECAST_ENABLE_DEBUG']

profile_name=""
if 'GET_FORECAST_AWS_PROFILE' in os.environ:
    profile_name=os.environ['GET_FORECAST_AWS_PROFILE']

columns_displayed = ["Account", "MTD", "Forecast", "Change"]
if 'GET_FORECAST_COLUMNS_DISPLAYED' in os.environ:
    columns_displayed=os.environ['GET_FORECAST_COLUMNS_DISPLAYED']
    columns_displayed = columns_displayed.split(',')

account_width=17
if 'GET_FORECAST_ACCOUNT_COLUMN_WIDTH' in os.environ:
    account_width=os.environ['GET_FORECAST_ACCOUNT_COLUMN_WIDTH']

output_format='text'
if 'GET_FORECAST_OUTPUT_FORMAT' in os.environ:
    output_format=os.environ['GET_FORECAST_OUTPUT_FORMAT']

utcnow = datetime.datetime.utcnow()
today = utcnow.strftime('%Y-%m-%d') 
first_day_of_month = utcnow.strftime('%Y-%m') + "-01"
first_day_next_month = (utcnow + relativedelta(months=1)).strftime("%Y-%m-01")
first_day_prior_month = (utcnow + relativedelta(months=-1)).strftime("%Y-%m-01")

if enable_debug != "" :
    print("today=",today)
    print("first_day_of_month=",first_day_of_month)
    print("first_day_next_month=",first_day_next_month)
    print("first_day_prior_month=",first_day_prior_month)

#create the session
session = None
if profile_name != "" :
    print("Setting AWS Proflie =",profile_name)
    session = boto3.session.Session(profile_name=profile_name)
else :
    session = boto3.session.Session()

output = calc_forecast(session)
format_rows = format_rows(output, account_width)

message=""
for line in format_rows :
    for column in columns_displayed :
        message += line.get(column)
    message += "\n"

if output_format == "slack" :
    print(message)
else:
    print(message)

