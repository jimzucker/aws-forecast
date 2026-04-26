"""Tests for alexa/interaction_model.json.

Regression guard: catch model files that won't build in the Alexa console
because of missing required intents or empty sample utterances.
"""
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = REPO_ROOT / "alexa" / "interaction_model.json"


REQUIRED_AMAZON_INTENTS = {
    "AMAZON.HelpIntent",
    "AMAZON.CancelIntent",
    "AMAZON.StopIntent",
    "AMAZON.FallbackIntent",
}


class InteractionModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with MODEL_PATH.open() as f:
            cls.model = json.load(f)

    def test_invocation_name_is_aws_cost(self):
        invocation = self.model["interactionModel"]["languageModel"]["invocationName"]
        self.assertEqual(invocation, "aws cost")

    def test_required_amazon_intents_present(self):
        intents = self.model["interactionModel"]["languageModel"]["intents"]
        names = {i["name"] for i in intents}
        for required in REQUIRED_AMAZON_INTENTS:
            self.assertIn(required, names, f"missing required intent {required}")

    def test_what_is_my_bill_intent_is_declared(self):
        intents = self.model["interactionModel"]["languageModel"]["intents"]
        names = {i["name"] for i in intents}
        self.assertIn("WhatIsMyBillIntent", names)

    def test_business_intent_has_sample_utterances(self):
        """Custom intents need at least one sample utterance for Alexa to build."""
        intents = self.model["interactionModel"]["languageModel"]["intents"]
        bill = next(i for i in intents if i["name"] == "WhatIsMyBillIntent")
        samples = bill.get("samples", [])
        self.assertGreater(len(samples), 0, "WhatIsMyBillIntent has no sample utterances")
        for sample in samples:
            self.assertTrue(sample.strip(), "empty sample utterance")

    def test_business_intent_includes_canonical_phrasing(self):
        intents = self.model["interactionModel"]["languageModel"]["intents"]
        bill = next(i for i in intents if i["name"] == "WhatIsMyBillIntent")
        samples = set(bill["samples"])
        # The phrase the README tells the user to say must be a sample utterance.
        self.assertIn("what is my current bill", samples)


if __name__ == "__main__":
    unittest.main()
