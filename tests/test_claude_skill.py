"""Structural tests for the Claude Code aws-cost-summary skill files."""
import json
import os
import shutil
import stat
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "aws-cost-summary"
SKILL_MD = SKILL_DIR / "SKILL.md"
RUN_SH = SKILL_DIR / "run.sh"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"


class SkillFilesTests(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(SKILL_MD.is_file(), f"missing {SKILL_MD}")

    def test_run_sh_exists(self):
        self.assertTrue(RUN_SH.is_file(), f"missing {RUN_SH}")

    def test_run_sh_is_executable(self):
        mode = RUN_SH.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR, "run.sh is not user-executable")

    def test_run_sh_is_syntactically_valid_bash(self):
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash not available on PATH")
        result = subprocess.run(
            [bash, "-n", str(RUN_SH)],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0,
                         f"bash -n failed: {result.stderr}")

    def test_run_sh_execs_get_forecast(self):
        text = RUN_SH.read_text()
        self.assertIn("exec python3", text)
        self.assertIn("get_forecast.py", text)

    def test_run_sh_sets_aws_profile_from_env(self):
        text = RUN_SH.read_text()
        self.assertIn("GET_FORECAST_AWS_PROFILE", text)
        self.assertIn("AWS_COST_PROFILE", text)


class SkillFrontmatterTests(unittest.TestCase):
    def test_skill_md_has_yaml_frontmatter(self):
        text = SKILL_MD.read_text()
        self.assertTrue(text.startswith("---\n"),
                        "SKILL.md must start with YAML frontmatter delimiter")
        end = text.find("\n---\n", 4)
        self.assertGreater(end, 0, "frontmatter is unterminated")

    def test_frontmatter_declares_name_and_description(self):
        import yaml
        text = SKILL_MD.read_text()
        end = text.find("\n---\n", 4)
        frontmatter = yaml.safe_load(text[4:end])
        self.assertIn("name", frontmatter)
        self.assertEqual(frontmatter["name"], "aws-cost-summary")
        self.assertIn("description", frontmatter)
        self.assertGreater(len(frontmatter["description"]), 20,
                           "description must be substantive enough for Claude's auto-trigger")


class SettingsJsonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = json.loads(SETTINGS.read_text())

    def test_settings_parses(self):
        self.assertIsInstance(self.settings, dict)

    def test_has_permissions_block(self):
        self.assertIn("permissions", self.settings)
        self.assertIn("allow", self.settings["permissions"])
        self.assertIn("deny", self.settings["permissions"])

    def test_allow_includes_run_script(self):
        allow = self.settings["permissions"]["allow"]
        self.assertTrue(
            any("run.sh" in entry for entry in allow),
            f"allow list must permit run.sh: {allow}",
        )

    def test_deny_blocks_iam_mutations(self):
        """Regression: don't accidentally widen the skill's blast radius."""
        deny = self.settings["permissions"]["deny"]
        required_substrings = [
            "aws iam",
            "aws lambda delete-function",
            "aws cloudformation delete-stack",
            "aws secretsmanager delete-secret",
            "aws ec2 terminate-instances",
        ]
        for needle in required_substrings:
            self.assertTrue(
                any(needle in entry for entry in deny),
                f"deny list missing entry containing '{needle}': {deny}",
            )


if __name__ == "__main__":
    unittest.main()
