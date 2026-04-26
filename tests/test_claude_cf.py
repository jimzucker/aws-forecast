"""Structural tests for claude_connector_cf.yaml.

Uses a minimal CFN-tag-aware YAML loader so PyYAML doesn't choke on `!Ref`,
`!GetAtt`, `!Sub`, `!Join`. We only care about resource shapes, not full
intrinsic-function evaluation.
"""
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
CF_PATH = REPO_ROOT / "claude_connector_cf.yaml"


class _CfnTag:
    def __init__(self, tag, value):
        self.tag = tag
        self.value = value

    def __repr__(self):  # pragma: no cover - debug only
        return f"CfnTag({self.tag!r}, {self.value!r})"


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
        resources = self.template["Resources"]
        types = {name: res["Type"] for name, res in resources.items()}
        type_set = set(types.values())
        for required in (
            "AWS::Lambda::Function",
            "AWS::Lambda::Url",
            "AWS::IAM::Role",
            "AWS::SecretsManager::Secret",
            "AWS::Lambda::Permission",
            "AWS::Logs::LogGroup",
        ):
            self.assertIn(required, type_set, f"missing resource type: {required}")

    def test_iam_role_has_no_wildcard_action(self):
        """Regression: lock down what the connector can do in CE/Orgs/STS."""
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
                    self.assertNotEqual(
                        action, "*",
                        f"IAM policy {policy['PolicyName']} has wildcard Action",
                    )

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
        expected = {
            "ce:GetCostAndUsage",
            "ce:GetCostForecast",
            "organizations:DescribeAccount",
            "sts:GetCallerIdentity",
            "secretsmanager:GetSecretValue",
        }
        self.assertEqual(set(actions), expected)

    def test_function_url_uses_none_auth_with_app_level_check(self):
        url = next(
            res for res in self.template["Resources"].values()
            if res["Type"] == "AWS::Lambda::Url"
        )
        self.assertEqual(url["Properties"]["AuthType"], "NONE")

    def test_lambda_runtime_is_python_3_12(self):
        fn = next(
            res for res in self.template["Resources"].values()
            if res["Type"] == "AWS::Lambda::Function"
        )
        self.assertEqual(fn["Properties"]["Runtime"], "python3.12")
        self.assertEqual(
            fn["Properties"]["Handler"],
            "claude_connector_handler.lambda_handler",
        )

    def test_outputs_expose_function_url_and_secret_arn(self):
        outputs = self.template.get("Outputs", {})
        self.assertIn("FunctionUrl", outputs)
        self.assertIn("BearerTokenSecretArn", outputs)


if __name__ == "__main__":
    unittest.main()
