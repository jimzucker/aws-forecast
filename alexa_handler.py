"""
Alexa skill Lambda for AWS Cost Summary.

Single business intent: WhatIsMyBillIntent. Plus the four required Amazon
intents (Help, Cancel, Stop, Fallback) and the LaunchRequest /
SessionEndedRequest envelopes.

Auth is provided by the Alexa Skills Kit principal (configured at the
Lambda permission level by alexa_skill_cf.yaml); no per-user credentials
flow through the Alexa surface.
"""
import logging

import boto3

import get_forecast


logger = logging.getLogger()
logger.setLevel(logging.INFO)


HELP_TEXT = (
    "Ask me 'what is my current bill' to hear your AWS month-to-date spend "
    "and forecast."
)
GOODBYE_TEXT = "Goodbye."
FALLBACK_TEXT = (
    "I didn't catch that. " + HELP_TEXT
)
COST_EXPLORER_DOWN_TEXT = (
    "I couldn't reach Cost Explorer right now. Please try again in a moment."
)


def _ssml_response(speech_text, end_session=True):
    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "SSML",
                "ssml": f"<speak>{speech_text}</speak>",
            },
            "shouldEndSession": end_session,
        },
    }


def _empty_response():
    return {"version": "1.0", "response": {}}


def _format_dollars(amount):
    return f"${amount:,.0f}"


def _bill_speech(rows):
    total = next((r for r in rows if r["account_name"] == "Total"), None)
    if total is None:
        return (
            "I couldn't find a total cost for your account. "
            "It may be a brand new account with no usage yet."
        )
    mtd = _format_dollars(total["amount_usage"])
    forecast = _format_dollars(total["amount_forecast"])
    variance = total["forecast_variance"]
    return (
        f"Your AWS month-to-date spend is {mtd}. "
        f"The forecast for this month is {forecast}, "
        f"a {variance:.0f} percent change from last month."
    )


def _handle_what_is_my_bill():
    try:
        session = boto3.session.Session()
        rows = get_forecast.calc_forecast(session)
    except Exception:
        logger.exception("calc_forecast failed in WhatIsMyBillIntent")
        return _ssml_response(COST_EXPLORER_DOWN_TEXT)
    return _ssml_response(_bill_speech(rows))


def _handle_intent(intent_name):
    if intent_name == "WhatIsMyBillIntent":
        return _handle_what_is_my_bill()
    if intent_name in ("AMAZON.HelpIntent",):
        return _ssml_response(HELP_TEXT, end_session=False)
    if intent_name in ("AMAZON.CancelIntent", "AMAZON.StopIntent"):
        return _ssml_response(GOODBYE_TEXT)
    if intent_name == "AMAZON.FallbackIntent":
        return _ssml_response(FALLBACK_TEXT, end_session=False)
    return _ssml_response(HELP_TEXT, end_session=False)


def lambda_handler(event, context):
    request = (event or {}).get("request") or {}
    request_type = request.get("type")

    if request_type == "LaunchRequest":
        return _ssml_response(HELP_TEXT, end_session=False)
    if request_type == "IntentRequest":
        intent_name = (request.get("intent") or {}).get("name", "")
        return _handle_intent(intent_name)
    if request_type == "SessionEndedRequest":
        return _empty_response()

    return _ssml_response(HELP_TEXT, end_session=False)
