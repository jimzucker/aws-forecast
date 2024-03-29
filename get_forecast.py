"""
Script to reproduce forecast $ (%) we see in the AWS Cost Explorer
Written by: Jim Zucker
Date: Sept 4, 2020

Commandline:
python3 get_forecast.py

Environment Variables:
    GET_FORECAST_COLUMNS_DISPLAYED - specify columnns and order 
        default: "Account,MTD,Forecast,Change"

    GET_FORECAST_ACCOUNT_COLUMN_WIDTH - max width for account name
        default: 17

    AWS_LAMBDA_FUNCTION_NAME - set if running in lambda, allows us to re-use the same .py on commandline for testing
    GET_FORECAST_AWS_PROFILE - set for test on command line

References
  * Calling Cost Explorer: https://aws.amazon.com/blogs/aws-cost-management/update-cost-explorer-forecasting-api-improvement/
  * Setup SNS: https://docs.aws.amazon.com/sns/latest/dg/sns-getting-started.html
  * Setup Slack as SNS subscriber: https://medium.com/cohealo-engineering/how-set-up-a-slack-channel-to-be-an-aws-sns-subscriber-63b4d57ad3ea

Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.
"""

import sys
import logging
import boto3
import os
import datetime
from dateutil.relativedelta import relativedelta
from botocore.exceptions import ClientError
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from base64 import b64decode

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger()


AWSGENIE_SECRET_MANAGER="awsgenie_secret_manager"
SLACK_SECRET_KEY_NAME="slack_url"
TEAMS_SECRET_KEY_NAME="teams_url"
SNS_SECRET_KEY_NAME="sns_arn"

AWS_LAMBDA_FUNCTION_NAME = ""
try:
    AWS_LAMBDA_FUNCTION_NAME = os.environ['AWS_LAMBDA_FUNCTION_NAME']
except Exception as e:
    logger.info("Not running as lambda")


def get_secret(sm_client):
    secret = ""
    try:
        secret = sm_client.get_secret_value( SecretId=AWSGENIE_SECRET_MANAGER )["SecretString"]
    except Exception as e:
        if e.response['Error']['Code'] == 'InvalidRequestException':
            logger.error("The request was invalid due to:", e)
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            logger.error("The request had invalid params:", e)

    return secret


def send_slack(slack_url, text_message):
    #make it a NOP if URL is NULL
    if slack_url == "":
        return

    #Slack and Teams have varying levels of support for mrkdown etc. This is provisioning for future use.
    slack_message = {
        'text': text_message 
    }

    req = Request(slack_url, json.dumps(slack_message).encode('utf-8'))
    try:
        response = urlopen(req)
        response.read()
        logger.debug("Message posted to slack")
    except HTTPError as e:
        logger.error("Request failed: %d %s", e.code, e.reason)
        logger.error("SLACK_URL= %s", slack_url)
        raise e
    except URLError as e:
        logger.error("Server connection failed: %s", e.reason)
        logger.error("slack_url= %s", slack_url)
        raise e
  
def send_teams(teams_url, text_message):
    #make it a NOP if URL is NULL
    if teams_url == "":
        return

    teams_message = {
        'text': text_message
    }

    req = Request(teams_url, json.dumps(teams_message).encode('utf-8'))
    try:
        response = urlopen(req)
        response.read()
        logger.debug("Message posted to teams")
    except HTTPError as e:
        logger.error("Request failed: %d %s", e.code, e.reason)
        logger.error("TEAMS_URL= %s", teams_url)
        raise e
    except URLError as e:
        logger.error("Server connection failed: %s", e.reason)
        logger.error("TEAMS_url=%s", teams_url)
        raise e

def send_sns(boto3_session, sns_arn, message):
    #make it a NOP if URL is NULL
    if sns_arn == "":
        return

    try:
        sns_client = boto3_session.client('sns')
        response = sns_client.publish(
            TopicArn=sns_arn,
            Message=message
        )
    except Exception as e:
        logger.error("SNS publish request failed ARN: %s", sns_arn)
        logger.error(e)


def display_output(boto3_session, message):
    secrets_manager_client = None
    secret = ""
    secrets_manager_client = boto3_session.client('secretsmanager')

    try:
        secret = get_secret(secrets_manager_client)
    except Exception as e:
        logger.debug("get_secret failed")
        print(e)

    try:
        slack_url = json.loads(secret)[SLACK_SECRET_KEY_NAME]
        send_slack(slack_url, message)
    except Exception as e:
        logger.info("Disabling Slack, URL not found")

    try:
        teams_url = json.loads(secret)[TEAMS_SECRET_KEY_NAME]
        send_teams(teams_url, message)
    except Exception as e:
        logger.info("Disabling Teams, URL not found", e)

    try:
        sns_arn=json.loads(secret)[SNS_SECRET_KEY_NAME]
        send_sns(boto3_session, sns_arn, message)
    except Exception as e:
        logger.info("Disabling SNS, Arn not found")
        
    print(message)


def calc_forecast(boto3_session):
    #create the clients we need for ce & org
    ce = boto3_session.client('ce')
    org = boto3_session.client('organizations')
    sts = boto3_session.client('sts')

    #initialize the standard filter
    not_filter= {
        "Not": {
            "Dimensions": {
                "Key": "RECORD_TYPE",
                "Values": [ "Credit", "Refund" ]
            }
        }
    }

    utcnow = datetime.datetime.utcnow()
    today = utcnow.strftime('%Y-%m-%d') 
    first_day_of_month = utcnow.strftime('%Y-%m') + "-01"
    first_day_next_month = (utcnow + relativedelta(months=1)).strftime("%Y-%m-01")
    first_day_prior_month = (utcnow + relativedelta(months=-1)).strftime("%Y-%m-01")

    logger.debug("today=",today)
    logger.debug("first_day_of_month=",first_day_of_month)
    logger.debug("first_day_next_month=",first_day_next_month)
    logger.debug("first_day_prior_month=",first_day_prior_month)


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
        "forecast_variance": forecast_variance
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

            try: 
                account_name=org.describe_account(AccountId=linked_account)['Account']['Name']
            except AWSOrganizationsNotInUseException as e:
                account_name=linked_account

            result = {
                "account_name": account_name,
                "amount_usage": amount_usage,
                "amount_forecast": amount_forecast,
                "forecast_variance": variance
            }
            output.append(result)

    return output


def format_rows(output,account_width):
    # print the heading
    mtd_width = 8
    forecast_width = 8
    change_width = 8

    output_rows = []

    # add new row for column headings
    row_headings = {
        "Account": "Account".ljust(account_width),
        "MTD": 'MTD'.ljust(mtd_width),
        "Forecast": "Forecast".ljust(forecast_width),
        "Change": "Change".ljust(change_width)
    }
    
    output_rows.append(row_headings)
    
    # add a separator row
    separator_row = {
        "Account": "".ljust(account_width, "-"),
        "MTD": "".ljust(mtd_width, "-"),
        "Forecast": "".ljust(forecast_width, "-"),
        "Change": "".ljust(change_width, "-")
    }

    output_rows.append(separator_row)
    
    
    # print in descending order by forecast
    lines = sorted(output, key=lambda k: k.get('amount_forecast'), reverse=True)
    for line in lines:
        if len(lines) == 2 and line.get('account_name') == 'Total':
            continue
        change = "{0:,.1f}%".format(line.get('forecast_variance'))
        row = {
            "Account": line.get('account_name')[:account_width].ljust(account_width),
            "MTD": "${0:,.0f}".format(line.get('amount_usage')).ljust(mtd_width),
            "Forecast": "${0:,.0f}".format(line.get('amount_forecast')).ljust(forecast_width),
            "Change": change.ljust(change_width)
        }
        output_rows.append(row)
    return output_rows

def publish_forecast(boto3_session) :
    #read params
    columns_displayed = ["Account", "Forecast", "Change"]
    if 'GET_FORECAST_COLUMNS_DISPLAYED' in os.environ:
        columns_displayed=os.environ['GET_FORECAST_COLUMNS_DISPLAYED']
        columns_displayed = columns_displayed.split(',')

    account_width=12
    if 'GET_FORECAST_ACCOUNT_COLUMN_WIDTH' in os.environ:
        account_width=os.environ['GET_FORECAST_ACCOUNT_COLUMN_WIDTH']

    output = calc_forecast(boto3_session)
    formated_rows = format_rows(output, account_width)

    message = ""
    for line in formated_rows:
        formated_line = ""
        for column in columns_displayed:
            if formated_line != "":
                formated_line += " | "
            formated_line += line.get(column)
        message += formated_line.rstrip() + "\n"

    code_block_format_message = '```\n' + message + '```\n'
    
    display_output(boto3_session, code_block_format_message)

def lambda_handler(event, context):
    try:
        publish_forecast(boto3)
    except Exception as e:
        print(e)
        raise Exception("Cannot connect to Cost Explorer with boto3")

def main():
    try:
        boto3_session = boto3.session.Session()
        if 'GET_FORECAST_AWS_PROFILE' in os.environ:
            profile_name=os.environ['GET_FORECAST_AWS_PROFILE']
            logger.info("Setting AWS Proflie ="+profile_name)
            boto3_session = boto3.session.Session(profile_name=profile_name)

        try:
            publish_forecast(boto3_session)
        except Exception as e:
            raise e

    except Exception as e:
        logger.error(e);
        sys.exit(1)

    sys.exit(0)

if __name__ == '__main__':
    main()
