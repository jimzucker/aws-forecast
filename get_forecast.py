"""
Script to reproduce forecast $ (%) we see in the AWS Cost Explorer
Written by: Jim Zucker
Date: Sept 4, 2020

Commandline:
python3 get_forecast.py --profile <account>  --type [FORECAST |ACTUALS]


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

import argparse
import sys
import logging
import boto3
from datetime import datetime
from dateutil.relativedelta import relativedelta
from botocore.exceptions import ClientError
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("info.log"),
        logging.StreamHandler()
    ])

logger = logging.getLogger()


def arg_parser():
    """Extracts various arguments from command line
    Args:
        None.

    Returns:
        obj: arguments parser.
    """

    def formatter(prog):
        return argparse.HelpFormatter(prog, width=100, max_help_position=100)

    parser = argparse.ArgumentParser(formatter_class=formatter)

    # define params:
    parser.add_argument('--profile', help=argparse.SUPPRESS, required=True, dest='profile')
    parser.add_argument('--type', help=argparse.SUPPRESS, required=True, dest='type')
    parser.add_argument('--d', help=argparse.SUPPRESS, required=False, action='store_true', dest='dry_run')
    parser.add_argument('--minutes', help=argparse.SUPPRESS, required=False, dest='minutes', default=30)
    parser.add_argument('--debug', help=argparse.SUPPRESS, required=False, action='store_true', dest='debug')

    # set parser:
    cmdline_params = parser.parse_args()
    return cmdline_params


def get_secret(client, secret_name):
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.error("The requested secret " + secret_name + " was not found")
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            logger.error("The request was invalid due to:", e)
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            logger.error("The request had invalid params:", e)
    else:
        # Secrets Manager decrypts the secret value using the associated KMS CMK
        # Depending on whether the secret was a string or binary, only one of these fields will be populated
        if 'SecretString' in get_secret_value_response:
            text_secret_data = json.loads(get_secret_value_response['SecretString']).get('slack_url')
        else:
            #binary_secret_data = get_secret_value_response['SecretBinary']
            logger.error("Binary Secrets not supported")

        # Your code goes here.
    return text_secret_data

#
# Calculates forecast, ignoring credits
#
def get_cost_forecast(costs_explorer_client, start_time, end_time):
    response = costs_explorer_client.get_cost_forecast(
        TimePeriod=dict(Start=start_time, End=end_time),
        Metric='BLENDED_COST',
        Granularity='MONTHLY',
        Filter={
            "Not": {
                "Dimensions": {
                    "Key": "RECORD_TYPE",
                    "Values": [
                        "Credit", "Refund"
                    ]
                }
            }
        }
    )

    return float(response['Total']['Amount'])

#
# used to calculate prior months and current months spend, excluding credits
#
def get_cost_and_usage(costs_explorer_client, first_day_of_prior_month, last_day_of_previous_month):
    response = costs_explorer_client.get_cost_and_usage(
        TimePeriod={
            'Start': first_day_of_prior_month,
            'End': last_day_of_previous_month
        },
        Granularity='MONTHLY',
        Filter={
            "Not": {
                "Dimensions": {
                    "Key": "RECORD_TYPE",
                    "Values": [
                        "Credit", "Refund"
                    ]
                }
            }
        },
        Metrics=[
            'BlendedCost',
        ]
    )

    return float(response['ResultsByTime'][0]['Total']['BlendedCost']['Amount'])


#
# Calculates forecast and % change from prior month
# note: We found we had to adjust dates for it to work saturday and sunday.  We also found that
#   on some days the forecast calls fail and we have to fall back to actuals 
#
def calc_forecast(costs_explorer_client):
    now = datetime.utcnow()  # current date and time

    # To get get_cost_forecast to work correctly 7 days a week we have to tweak the start end dates a bit.
    # Also some days even this failes towards the end of the month and we have to switch to showing actuals

    # check if it is a weekend mon=1..sun=7 and move to monyda
    week_day = now.isoweekday()
    cost_type = "Forecast"
    if week_day >= 5:
        days_check = 7 - now.isoweekday() + 1
        start_time = (now + relativedelta(days=days_check)).strftime("%Y-%m-%d")
    else:
        start_time = (now + relativedelta(days=1)).strftime("%Y-%m-%d")

        # this is always the first of the next month
    end_time = (now + relativedelta(months=1)).strftime("%Y-%m-01")

    try:
        current_month_forecast = get_cost_forecast(costs_explorer_client, start_time, end_time)
    except Exception as e:
        logger.warning("WARNING: Cannot forecast, falling back to Actuals, start_time=", start_time, " ,end_time=", end_time, "\n")

        # when an account is new forecast wil not work and you have to use actuals
        start_time = (now.replace(day=1)).strftime("%Y-%m-%d")
        end_time = now.strftime("%Y-%m-%d")
        try:
            cost_type = "Actuals(MTD - not enought data to forecast)"
            current_month_forecast = get_cost_and_usage(costs_explorer_client, start_time, end_time)
        except Exception as e:
            cost_type = "Error cannot calculate forecast"
            current_month_forecast = 0
            error_message = f"Exception calculating Current Month, start_time={start_time} end_time={end_time}\n {e}"
            logger.error(error_message);

    # get last months bill
    first_day_of_prior_month = (now + relativedelta(months=-1)).replace(day=1).strftime("%Y-%m-%d")
    last_day_of_previous_month = (now.replace(day=1) + relativedelta(days=-1)).strftime("%Y-%m-%d")

    try:
        prior_month_bill = get_cost_and_usage(costs_explorer_client, first_day_of_prior_month, last_day_of_previous_month)
    except Exception as e:
        prior_month_bill = 0
        error_message = f"Error: Exception calculating Prior Month, first_day_of_prior_month=" \
                        f"{first_day_of_prior_month} last_day_of_previous_month={last_day_of_previous_month}\n {e}"
        logger.error(error_message);

    pct_change = 0
    if current_month_forecast != 0:
        pct_change = (1 - prior_month_bill / current_month_forecast) * 100

    return cost_type + ": ${0:,.0f}".format(float(current_month_forecast)) + " ({0:+.2f}%)".format(pct_change)

def display_output(forecast_slack_url,message):
    if forecast_slack_url != "":
        send_slack(forecast_slack_url, message)
    else:
        logger.info(message)

def send_slack(slack_hook_url, message):
    slack_message = {
        'text': message
    }

    req = Request(slack_hook_url, json.dumps(slack_message).encode('utf-8'))

    try:
        response = urlopen(req)
        response.read()
        logger.debug("Message posted to slack")
    except HTTPError as e:
        logger.error("Request failed: %d %s", e.code, e.reason)
    except URLError as e:
        logger.error("Server connection failed: %s", e.reason)

def get_forecast():
    try:
        cmdline_params = arg_parser()
        boto3_session = boto3.Session(profile_name=cmdline_params.profile)
        costs_explorer_client = boto3_session.client('ce')

        forecast_slack_url=""
        try:
            secrets_manager_client = boto3_session.client('secretsmanager')
            forecast_slack_url='https://' + get_secret(secrets_manager_client, "awsgenie_forecast_slack_url")
        except Exception as e:
            logger.warning("Disabling Slack URL not found")

        if cmdline_params.type in ['FORECAST']:
            forecast = calc_forecast(costs_explorer_client)
            display_output(forecast_slack_url, forecast)
        elif cmdline_params.type in ['ACTUALS']:
            raise Exception("not implimented - ACTUALS")
            actuals = calc_forecast(costs_explorer_client)
            display_output(forecast_slack_url, actuals)
        else:
            print("Invalid run type: cmdline_params.type . Please choose from: FORECAST, ACTUALS")
            sys.exit(1)

    except Exception as e:
        error_message = f"Error: {e}\n {traceback.format_exc()}"
        logger.error(error_message);
        sys.exit(1)

    sys.exit(0)

if __name__ == '__main__':
    get_forecast()
