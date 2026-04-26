"""Sanity tests for claude_connector_openapi.yaml."""
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "claude_connector_openapi.yaml"


class OpenApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with SPEC_PATH.open() as f:
            cls.spec = yaml.safe_load(f)

    def test_spec_parses_as_openapi_3_1(self):
        self.assertTrue(self.spec["openapi"].startswith("3."))

    def test_has_servers_block_for_url_substitution(self):
        servers = self.spec.get("servers")
        self.assertIsInstance(servers, list)
        self.assertGreater(len(servers), 0)
        self.assertIn("url", servers[0])

    def test_declares_bearer_auth_scheme(self):
        schemes = self.spec["components"]["securitySchemes"]
        self.assertIn("bearerAuth", schemes)
        self.assertEqual(schemes["bearerAuth"]["type"], "http")
        self.assertEqual(schemes["bearerAuth"]["scheme"], "bearer")

    def test_exactly_one_post_root_operation(self):
        ops = self.spec["paths"]["/"]
        methods = {m for m in ops if m in {"get", "post", "put", "delete", "patch"}}
        self.assertEqual(methods, {"post"})
        post = ops["post"]
        self.assertIn("operationId", post)
        self.assertEqual(post["operationId"], "getCostSummary")
        # Operation requires bearer auth.
        self.assertIn("security", post)
        self.assertEqual(post["security"], [{"bearerAuth": []}])

    def test_response_schema_matches_handler_payload_shape(self):
        """Response schema CostSummary must declare the same keys the handler returns."""
        schema = self.spec["components"]["schemas"]["CostSummary"]
        required = set(schema["required"])
        self.assertEqual(
            required,
            {"total_mtd", "total_forecast", "percent_change", "accounts"},
        )
        account = self.spec["components"]["schemas"]["AccountSummary"]
        self.assertEqual(
            set(account["required"]),
            {"name", "mtd", "forecast", "percent_change"},
        )

    def test_documents_401_and_500(self):
        responses = self.spec["paths"]["/"]["post"]["responses"]
        self.assertIn("200", responses)
        self.assertIn("401", responses)
        self.assertIn("500", responses)


if __name__ == "__main__":
    unittest.main()
