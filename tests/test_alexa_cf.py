"""Structural tests for alexa_skill_cf.yaml."""
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
CF_PATH = REPO_ROOT / "alexa_skill_cf.yaml"


class _CfnTag:
    def __init__(self, tag, value):
        self.tag = tag
        self.value = value


def _make_cfn_loader():
    class _Loader(yaml.SafeLoader):
        pass

    def _construct(loader, tag_suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return _CfnTag(tag_suffix, loader.construct_scalar(node))
        if isinstance(node, yaml.SequenceNode):
            return _CfnTag(tag_suffix, loader.construct_sequence(node, deep=True))
        if isinstance(node, yaml.MappingNode):
            return _CfnTag(tag_suffix, loader.construct_mapping(node, deep=True))
        raise yaml.YAMLError(f"unexpected node kind: {node!r}")

    _Loader.add_multi_constructor("!", _construct)
    return _Loader


def _load_cfn(path):
    with path.open() as f:
        return yaml.load(f, Loader=_make_cfn_loader())


class CloudFormationTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = _load_cfn(CF_PATH)

    def test_template_parses(self):
        self.assertIsInstance(self.template, dict)
        self.assertEqual(self.template["AWSTemplateFormatVersion"], "2010-09-09")

    def test_required_resources_present(self):
        types = {res["Type"] for res in self.template["Resources"].values()}
        for required in (
            "AWS::Lambda::Function",
            "AWS::IAM::Role",
            "AWS::Lambda::Permission",
            "AWS::Logs::LogGroup",
        ):
            self.assertIn(required, types, f"missing resource type: {required}")

    def test_no_secrets_manager_resource(self):
        """Alexa is auth'd by the ASK principal — no bearer token needed."""
        types = {res["Type"] for res in self.template["Resources"].values()}
        self.assertNotIn("AWS::SecretsManager::Secret", types)

    def test_alexa_permission_uses_ask_principal(self):
        perm = next(
            res for res in self.template["Resources"].values()
            if res["Type"] == "AWS::Lambda::Permission"
        )
        self.assertEqual(perm["Properties"]["Principal"], "alexa-appkit.amazon.com")
        self.assertEqual(perm["Properties"]["Action"], "lambda:InvokeFunction")
        # EventSourceToken must reference the AlexaSkillId parameter so only
        # the user's own skill can invoke this Lambda.
        token = perm["Properties"]["EventSourceToken"]
        self.assertIsInstance(token, _CfnTag)
        self.assertEqual(token.tag, "Ref")
        self.assertEqual(token.value, "AlexaSkillId")

    def test_alexa_skill_id_parameter_validated(self):
        import re
        params = self.template["Parameters"]
        self.assertIn("AlexaSkillId", params)
        pattern = params["AlexaSkillId"].get("AllowedPattern", "")
        self.assertTrue(pattern, "AlexaSkillId must declare an AllowedPattern")
        # Pattern must accept the canonical Alexa skill ID format and reject
        # unrelated input.
        regex = re.compile(pattern)
        self.assertTrue(regex.match("amzn1.ask.skill.abc-123-def"))
        self.assertIsNone(regex.match("not-a-skill-id"))
        self.assertIsNone(regex.match("amzn1.ask.account.foo"))

    def test_iam_role_has_no_wildcard_action(self):
        role = next(
            res for res in self.template["Resources"].values()
            if res["Type"] == "AWS::IAM::Role"
        )
        for policy in role["Properties"]["Policies"]:
            for stmt in policy["PolicyDocument"]["Statement"]:
                actions = stmt["Action"]
                if isinstance(actions, str):
                    actions = [actions]
                for action in actions:
                    self.assertNotEqual(action, "*",
                                        f"wildcard Action in {policy['PolicyName']}")

    def test_iam_role_grants_only_documented_actions(self):
        role = next(
            res for res in self.template["Resources"].values()
            if res["Type"] == "AWS::IAM::Role"
        )
        actions = []
        for policy in role["Properties"]["Policies"]:
            for stmt in policy["PolicyDocument"]["Statement"]:
                a = stmt["Action"]
                actions.extend(a if isinstance(a, list) else [a])
        # Alexa needs no Secrets Manager access; the bearer-token pattern
        # doesn't apply here.
        expected = {
            "ce:GetCostAndUsage",
            "ce:GetCostForecast",
            "organizations:DescribeAccount",
            "sts:GetCallerIdentity",
        }
        self.assertEqual(set(actions), expected)

    def test_lambda_runtime_and_handler(self):
        fn = next(
            res for res in self.template["Resources"].values()
            if res["Type"] == "AWS::Lambda::Function"
        )
        self.assertEqual(fn["Properties"]["Runtime"], "python3.12")
        self.assertEqual(fn["Properties"]["Handler"], "alexa_handler.lambda_handler")

    def test_outputs_expose_lambda_arn(self):
        outputs = self.template.get("Outputs", {})
        self.assertIn("LambdaArn", outputs)


if __name__ == "__main__":
    unittest.main()
