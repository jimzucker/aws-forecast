import argparse
import boto3
import datetime
from dateutil.relativedelta import relativedelta

utcnow = datetime.datetime.utcnow()
today = utcnow.strftime('%Y-%m-%d') 
first_day_of_month = utcnow.strftime('%Y-%m') + "-01"
first_day_next_month = (utcnow + relativedelta(months=1)).strftime("%Y-%m-01")
first_day_prior_month = (utcnow + relativedelta(months=-1)).strftime("%Y-%m-01")

#print("today=",today)
#print("first_day_of_month=",first_day_of_month)
#print("first_day_next_month=",first_day_next_month)
#print("first_day_prior_month=",first_day_prior_month)

#parse params (we optioanally support --profile)
parser = argparse.ArgumentParser()
parser.add_argument('--profile', default="")
args = parser.parse_args()

#create the session
session = None
if args.profile != "" :
    print("Setting AWS Proflie =",args.profile)
    session = boto3.session.Session(profile_name=args.profile)
else :
    print("Using Default AWS Proflie")
    session = boto3.session.Session()

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

data = ce.get_cost_and_usage(
    TimePeriod={'Start': first_day_prior_month, 'End':  first_day_of_month}
    , Granularity='MONTHLY', Metrics=['UnblendedCost'], Filter=not_filter
    )
results = data['ResultsByTime']
amount_usage_prior_month = float(results[0]['Total']['UnblendedCost']['Amount'])

#Total Forecast
data = ce.get_cost_forecast(
    TimePeriod={'Start': today, 'End':  first_day_next_month}
    , Granularity='MONTHLY', Metric='UNBLENDED_COST', Filter=not_filter
    )
amount_forecast = float(data['Total']['Amount'])
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
        #get prior-month usage
        data = ce.get_cost_and_usage(
            TimePeriod={'Start': first_day_prior_month, 'End':  first_day_of_month}
            , Granularity='MONTHLY', Metrics=['UnblendedCost'], Filter=linked_account_filter
            )
        results = data['ResultsByTime']
        amount_usage_prior_month = float(results[0]['Total']['UnblendedCost']['Amount']) 

        #Forecast
        data = ce.get_cost_forecast(
            TimePeriod={'Start': today, 'End':  first_day_next_month}
            , Granularity='MONTHLY', Metric='UNBLENDED_COST', Filter=linked_account_filter
            )
        amount_forecast = float(data['Total']['Amount'])

        account_name=org.describe_account(AccountId=linked_account)['Account']['Name']
        result = {
            "account_name": account_name,
            "amount_usage": amount_usage,
            "amount_forecast": amount_forecast,
            "forecast_variance": (amount_forecast-amount_usage_prior_month) / amount_usage_prior_month *100
        }
        output.append(result)

#print the heading
print('Account'.ljust(18)
#    , 'MTD'.rjust(8)
    , 'Forecast'
 #   , 'Change'.rjust(8)
)

#print in decending order by forecast
lines = sorted(output, key=lambda k: k.get('amount_forecast'), reverse=True)
for line in lines :
    if len(lines) == 2 and line.get('account_name') == 'Total':
        break
    variance = "{0:,.1f}%".format(line.get('forecast_variance'))
    print(line.get('account_name')[:17].ljust(18)
        , "${0:,.0f}".format(line.get('amount_forecast')).rjust(8) + variance.rjust(7)
 #   , "${0:,.0f}".format(line.get('amount_usage')).rjust(8)
  #  , "${0:,.0f}".format(line.get('amount_forecast')).rjust(8)
  #  , "{0:,.2f}%".format(line.get('forecast_variance')).rjust(8)
    )




