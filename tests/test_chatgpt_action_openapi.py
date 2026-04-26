"""Sanity tests for chatgpt_action_openapi.yaml.

ChatGPT Custom GPT Actions impose constraints beyond standard OpenAPI:
- A `servers[]` block with at least one URL.
- Every operation must have a unique, non-empty `operationId`.
- Total operations <= 30.
- Authentication declared via `securitySchemes`.
"""
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "chatgpt_action_openapi.yaml"

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head"}


class OpenApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with SPEC_PATH.open() as f:
            cls.spec = yaml.safe_load(f)

    def test_spec_parses_as_openapi_3(self):
        self.assertTrue(self.spec["openapi"].startswith("3."))

    def test_has_servers_block(self):
        """ChatGPT requires servers[] — Custom GPT builder rejects schemas without it."""
        servers = self.spec.get("servers")
        self.assertIsInstance(servers, list)
        self.assertGreater(len(servers), 0)
        self.assertIn("url", servers[0])
        self.assertTrue(servers[0]["url"].startswith("https://"))

    def test_every_operation_has_unique_operation_id(self):
        op_ids = []
        for path, methods in self.spec["paths"].items():
            for method, op in methods.items():
                if method.lower() not in HTTP_METHODS:
                    continue
                self.assertIn("operationId", op,
                              f"{method.upper()} {path} missing operationId")
                self.assertTrue(op["operationId"].strip(),
                                f"{method.upper()} {path} has empty operationId")
                op_ids.append(op["operationId"])
        self.assertEqual(len(op_ids), len(set(op_ids)), "operationIds must be unique")

    def test_at_most_30_operations(self):
        """ChatGPT GPT builder caps Actions at 30 operations per schema."""
        count = 0
        for methods in self.spec["paths"].values():
            count += sum(1 for m in methods if m.lower() in HTTP_METHODS)
        self.assertLessEqual(count, 30)

    def test_declares_bearer_auth(self):
        schemes = self.spec["components"]["securitySchemes"]
        self.assertIn("bearerAuth", schemes)
        self.assertEqual(schemes["bearerAuth"]["type"], "http")
        self.assertEqual(schemes["bearerAuth"]["scheme"], "bearer")

    def test_post_root_operation_uses_bearer_auth(self):
        post = self.spec["paths"]["/"]["post"]
        self.assertEqual(post["operationId"], "getCostSummary")
        self.assertEqual(post.get("security"), [{"bearerAuth": []}])

    def test_response_schema_matches_handler_payload(self):
        cs = self.spec["components"]["schemas"]["CostSummary"]
        self.assertEqual(
            set(cs["required"]),
            {"total_mtd", "total_forecast", "percent_change", "accounts"},
        )
        ac = self.spec["components"]["schemas"]["AccountSummary"]
        self.assertEqual(
            set(ac["required"]),
            {"name", "mtd", "forecast", "percent_change"},
        )

    def test_documents_401_and_500(self):
        responses = self.spec["paths"]["/"]["post"]["responses"]
        for code in ("200", "401", "500"):
            self.assertIn(code, responses, f"missing response code {code}")


if __name__ == "__main__":
    unittest.main()
