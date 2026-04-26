"""Unit tests for alexa_handler.lambda_handler."""
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

import alexa_handler as handler
from tests._helpers import make_mock_boto3_session


CALC_ROWS = [
    {"account_name": "Total", "amount_usage": 1234.0,
     "amount_forecast": 5678.0, "forecast_variance": 78.0},
    {"account_name": "alpha", "amount_usage": 100.0,
     "amount_forecast": 200.0, "forecast_variance": 100.0},
]


def _launch():
    return {"version": "1.0", "request": {"type": "LaunchRequest"}}


def _intent(name):
    return {
        "version": "1.0",
        "request": {"type": "IntentRequest", "intent": {"name": name}},
    }


def _session_ended():
    return {"version": "1.0", "request": {"type": "SessionEndedRequest"}}


def _patch_session(session):
    return patch.object(handler.boto3.session, "Session", return_value=session)


class EnvelopeShapeTests(unittest.TestCase):
    def test_launch_response_envelope_has_required_keys(self):
        response = handler.lambda_handler(_launch(), None)
        self.assertEqual(response["version"], "1.0")
        self.assertIn("response", response)
        self.assertIn("outputSpeech", response["response"])
        self.assertEqual(response["response"]["outputSpeech"]["type"], "SSML")
        self.assertIn("ssml", response["response"]["outputSpeech"])

    def test_ssml_is_well_formed_xml(self):
        session = make_mock_boto3_session()
        with _patch_session(session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=CALC_ROWS):
            response = handler.lambda_handler(_intent("WhatIsMyBillIntent"), None)
        ssml = response["response"]["outputSpeech"]["ssml"]
        # Must be valid XML so Alexa's TTS doesn't choke on it.
        ET.fromstring(ssml)
        self.assertTrue(ssml.startswith("<speak>"))
        self.assertTrue(ssml.endswith("</speak>"))


class LaunchRequestTests(unittest.TestCase):
    def test_does_not_end_session(self):
        response = handler.lambda_handler(_launch(), None)
        self.assertFalse(response["response"]["shouldEndSession"])

    def test_speaks_help_text(self):
        response = handler.lambda_handler(_launch(), None)
        self.assertIn("what is my current bill",
                      response["response"]["outputSpeech"]["ssml"])

    def test_does_not_call_calc_forecast(self):
        with patch.object(handler.get_forecast, "calc_forecast") as calc:
            handler.lambda_handler(_launch(), None)
            calc.assert_not_called()


class WhatIsMyBillIntentTests(unittest.TestCase):
    def setUp(self):
        self.session = make_mock_boto3_session()

    def test_calls_calc_forecast_once(self):
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast",
                          return_value=CALC_ROWS) as calc:
            handler.lambda_handler(_intent("WhatIsMyBillIntent"), None)
            calc.assert_called_once()

    def test_speaks_total_dollars(self):
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=CALC_ROWS):
            response = handler.lambda_handler(_intent("WhatIsMyBillIntent"), None)
        ssml = response["response"]["outputSpeech"]["ssml"]
        # The Total row from CALC_ROWS has $1,234 MTD and $5,678 forecast.
        self.assertIn("$1,234", ssml)
        self.assertIn("$5,678", ssml)

    def test_speaks_percent_change(self):
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=CALC_ROWS):
            response = handler.lambda_handler(_intent("WhatIsMyBillIntent"), None)
        ssml = response["response"]["outputSpeech"]["ssml"]
        self.assertIn("78 percent", ssml)

    def test_calc_forecast_failure_returns_graceful_ssml(self):
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast",
                          side_effect=RuntimeError("ce down")):
            response = handler.lambda_handler(_intent("WhatIsMyBillIntent"), None)
        # Must NOT 500. Must speak a friendly message.
        self.assertEqual(response["version"], "1.0")
        ssml = response["response"]["outputSpeech"]["ssml"]
        self.assertIn("couldn't reach Cost Explorer", ssml)
        self.assertNotIn("ce down", ssml)
        self.assertNotIn("Traceback", ssml)

    def test_no_total_row_speaks_friendly_fallback(self):
        rows = [r for r in CALC_ROWS if r["account_name"] != "Total"]
        with _patch_session(self.session), \
             patch.object(handler.get_forecast, "calc_forecast", return_value=rows):
            response = handler.lambda_handler(_intent("WhatIsMyBillIntent"), None)
        ssml = response["response"]["outputSpeech"]["ssml"]
        self.assertIn("brand new account", ssml)


class CannedIntentTests(unittest.TestCase):
    def test_help_intent_does_not_end_session(self):
        response = handler.lambda_handler(_intent("AMAZON.HelpIntent"), None)
        self.assertFalse(response["response"]["shouldEndSession"])
        self.assertIn("what is my current bill",
                      response["response"]["outputSpeech"]["ssml"])

    def test_cancel_intent_says_goodbye_and_ends(self):
        response = handler.lambda_handler(_intent("AMAZON.CancelIntent"), None)
        self.assertTrue(response["response"]["shouldEndSession"])
        self.assertIn("Goodbye", response["response"]["outputSpeech"]["ssml"])

    def test_stop_intent_says_goodbye_and_ends(self):
        response = handler.lambda_handler(_intent("AMAZON.StopIntent"), None)
        self.assertTrue(response["response"]["shouldEndSession"])
        self.assertIn("Goodbye", response["response"]["outputSpeech"]["ssml"])

    def test_fallback_intent_does_not_end_session(self):
        response = handler.lambda_handler(_intent("AMAZON.FallbackIntent"), None)
        self.assertFalse(response["response"]["shouldEndSession"])

    def test_unknown_intent_returns_help(self):
        response = handler.lambda_handler(_intent("FooBarIntent"), None)
        self.assertFalse(response["response"]["shouldEndSession"])
        self.assertIn("what is my current bill",
                      response["response"]["outputSpeech"]["ssml"])


class SessionEndedRequestTests(unittest.TestCase):
    def test_returns_empty_response_envelope(self):
        response = handler.lambda_handler(_session_ended(), None)
        self.assertEqual(response, {"version": "1.0", "response": {}})

    def test_does_not_call_calc_forecast(self):
        with patch.object(handler.get_forecast, "calc_forecast") as calc:
            handler.lambda_handler(_session_ended(), None)
            calc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
