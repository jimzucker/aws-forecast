"""
Script to reproduce forecast $ (%) we see in the AWS Cost Explorer
Written by: Jim Zucker
Date: Sept 4, 2020

Commandline:
python3 get_forecast.py --profile <account>  --type [FORECAST |ACTUALS]

References
  * Setup SNS: https://docs.aws.amazon.com/sns/latest/dg/sns-getting-started.html
  * Setup Slack as SNS subscriber: https://medium.com/cohealo-engineering/how-set-up-a-slack-channel-to-be-an-aws-sns-subscriber-63b4d57ad3ea
  * Setup Lambda to Slack: 


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
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from botocore.exceptions import ClientError
import json
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from base64 import b64decode


# Initialize you log configuration using the base class
logging.basicConfig(level = logging.INFO)
logger = logging.getLogger()

    
AWSGENIE_SECRET_MANAGER="awsgenie_secret_manager"
SLACK_SECRET_KEY_NAME="slack_url"
SNS_SECRET_KEY_NAME="sns_arn"

AWS_LAMBDA_FUNCTION_NAME = ""
try:
    AWS_LAMBDA_FUNCTION_NAME = os.environ['AWS_LAMBDA_FUNCTION_NAME']
except Exception as e:
    logger.info("Not running as lambda")

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
#    parser.add_argument('--debug', help=argparse.SUPPRESS, required=False, action='store_true', dest='debug')

    # set parser:
    cmdline_params = parser.parse_args()
    return cmdline_params


def get_secret(sm_client,secret_key_name):
    # if AWS_LAMBDA_FUNCTION_NAME == "":
    try:
        text_secret_data = ""
        get_secret_value_response = sm_client.get_secret_value( SecretId=AWSGENIE_SECRET_MANAGER )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.error("The requested secret " + secret_name + " was not found")
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            logger.error("The request was invalid due to:", e)
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            logger.error("The request had invalid params:", e)

    # Secrets Manager decrypts the secret value using the associated KMS CMK
    # Depending on whether the secret was a string or binary, only one of these fields will be populated
    if 'SecretString' in get_secret_value_response:
        text_secret_data = json.loads(get_secret_value_response['SecretString']).get(secret_key_name)
    else:
        #binary_secret_data = get_secret_value_response['SecretBinary']
        logger.error("Binary Secrets not supported")

        # Your code goes here.
    return text_secret_data
    # else:
    #     return ""

def send_slack(slack_url, message):
    #make it a NOP if URL is NULL
    if slack_url == "":
        return

    slack_message = {
        'text': message
    }

    req = Request(slack_url, json.dumps(slack_message).encode('utf-8'))
    try:
        response = urlopen(req)
        response.read()
        logger.debug("Message posted to slack")
    except HTTPError as e:
        logger.error("Request failed: %d %s", e.code, e.reason)
        logger.error("SLACK_URL= %s", slack_url)
    except URLError as e:
        logger.error("Server connection failed: %s", e.reason)
        logger.error("slack_url= %s", slack_url)

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
    slack_url=""
    sns_arn=""
    # if AWS_LAMBDA_FUNCTION_NAME != "" :
    #     try:
    #         # The base-64 encoded, encrypted key (CiphertextBlob) stored in the kmsEncryptedHookUrl environment variable
    #         ENCRYPTED_PARAM = os.environ[SLACK_SECRET_KEY_NAME]
    #         logger.info("ENCRYPTED_PARAM $s", ENCRYPTED_PARAM
    #                     )
    #         # The Slack channel to send a message to stored in the slackChannel environment variable
    #         slack_url = "https://" + boto3.client('kms').decrypt(
    #             CiphertextBlob=b64decode(ENCRYPTED_PARAM),
    #             EncryptionContext={'LambdaFunctionName': AWS_LAMBDA_FUNCTION_NAME}
    #         )['Plaintext'].decode('utf-8')
    #
    #
    #     except Exception as e:
    #         logger.warning("Disabling Slack URL not found")
    #
    #     try:
    #         # The base-64 encoded, encrypted key (CiphertextBlob) stored in the kmsEncryptedHookUrl environment variable
    #         ENCRYPTED_PARAM = os.environ[SNS_SECRET_KEY_NAME]
    #         logger.info("ENCRYPTED_PARAM $s", ENCRYPTED_PARAM)
    #
    #         # The Slack channel to send a message to stored in the slackChannel environment variable
    #         sns_arn = boto3.client('kms').decrypt(
    #             CiphertextBlob=b64decode(ENCRYPTED_PARAM),
    #             EncryptionContext={'LambdaFunctionName': AWS_LAMBDA_FUNCTION_NAME}
    #         )['Plaintext'].decode('utf-8')
    #     except Exception as e:
    #         logger.warning("Disabling SNS Arn not found")
    #
    #     if slack_url == "" and sns_arn == "":
    #         logger.error("SNS & Slack disabled Lambda will not work")
    #         raise Exception("Error: SNS & Slack disabled Lambda will not work")
    #
    # else:
    secrets_manager_client = boto3_session.client('secretsmanager')
    try:
        slack_url='https://' + get_secret(secrets_manager_client, SLACK_SECRET_KEY_NAME)
    except Exception as e:
        logger.warning("Disabling Slack URL not found")

    try:
        sns_arn=get_secret(secrets_manager_client, SNS_SECRET_KEY_NAME)
    except Exception as e:
        logger.warning("Disabling SNS Arn not found")

    send_slack(slack_url, message)
    send_sns(boto3_session, sns_arn, message)
    print(message)


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
def calc_forecast(boto3_session):
    costs_explorer_client = boto3_session.client('ce')
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

def get_forecast(boto3_session, type):
    if type in ['FORECAST']:
        forecast = calc_forecast(boto3_session)
        display_output(boto3_session, forecast)
    elif type in ['ACTUALS']:
        raise Exception("not implimented - ACTUALS")
    else:
        raise Exception("Invalid run type: cmdline_params.type . Please choose from: FORECAST, ACTUALS")

    return forecast

def lambda_handler(event, context):
    try:
        get_forecast(boto3, "FORECAST")
    except Exception as e:
        print(e)
        raise Exception("Cannot connect to Cost Explorer with boto3")

def main():
    try:
        cmdline_params = arg_parser()
        boto3_session = boto3.Session(profile_name=cmdline_params.profile)

        try:
            get_forecast(boto3_session, cmdline_params.type)
        except Exception as e:
            raise Exception("Cannot connect to Cost Explorer with boto3")

    except Exception as e:
        logger.error("Cannot connect to boto3");
        logger.error(e);
        sys.exit(1)

    sys.exit(0)

if __name__ == '__main__':
    main()
