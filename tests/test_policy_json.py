import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score.config import CONFIG_NAME, SCHEMA_URL, ConfigError, Policy, load_policy, parse_policy
from agent_config_score.doctor import _check_config
from agent_config_score.entrypoint import main


AMBIGUOUS = '{"policy":{"fail_under":90,"fail_under":0}}'


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True,
        text=True, encoding="utf-8", timeout=30,
    ).stdout.strip()


class PolicyJsonTests(unittest.TestCase):
    def _load_text(self, text):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / CONFIG_NAME).write_text(text, encoding="utf-8")
            return load_policy(root)

    def test_duplicate_root_members_are_rejected(self):
        for text in (
            '{"policy":{"max_drop":0},"policy":{"max_drop":100}}',
            '{"version":1,"version":1}',
            '{"suppressions":[],"suppressions":[]}',
            '{"$schema":"first","$schema":"second"}',
        ):
            with self.subTest(text=text), self.assertRaisesRegex(ConfigError, "duplicate JSON member"):
                self._load_text(text)

    def test_duplicate_nested_policy_members_are_rejected(self):
        for text in (
            AMBIGUOUS,
            '{"policy":{"max_drop":0,"max_drop":100}}',
            '{"policy":{"fail_on_new_errors":true,"fail_on_new_errors":false}}',
            '{"policy":{"fail_under":90,"fail_under":90}}',
        ):
            with self.subTest(text=text), self.assertRaisesRegex(ConfigError, "duplicate JSON member"):
                self._load_text(text)

    def test_duplicate_suppression_members_are_rejected(self):
        for member in (
            '"rule":"dead-path","rule":"curl-pipe-shell"',
            '"reason":"first","reason":"second"',
            '"expires":"2098-01-01","expires":"2099-01-01"',
            '"paths":["AGENTS.md"],"paths":["**"]',
        ):
            text = '{"suppressions":[{' + member + '}]}'
            with self.subTest(member=member), self.assertRaisesRegex(ConfigError, "duplicate JSON member"):
                self._load_text(text)

    def test_duplicate_detection_uses_decoded_json_names(self):
        text = r'{"policy":{"fail_under":90,"fail\u005funder":0}}'
        with self.assertRaisesRegex(ConfigError, "duplicate JSON member"):
            self._load_text(text)

    def test_duplicate_error_does_not_echo_member_names_or_values(self):
        text = '{"synthetic-private-key":"synthetic-private-value","synthetic-private-key":0}'
        with self.assertRaises(ConfigError) as raised:
            self._load_text(text)
        self.assertIn("duplicate JSON member", str(raised.exception))
        self.assertNotIn("synthetic-private", str(raised.exception))

    def test_nonstandard_json_number_constants_are_rejected(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant), self.assertRaisesRegex(ConfigError, "non-standard JSON number"):
                self._load_text('{"version":' + constant + '}')

    def test_boolean_is_not_a_config_format_version(self):
        for version in (True, False):
            with self.subTest(version=version), self.assertRaisesRegex(ConfigError, "version must be 1"):
                parse_policy({"version": version})

    def test_valid_configuration_defaults_and_numeric_version_are_preserved(self):
        self.assertEqual(self._load_text('{}'), Policy())
        self.assertEqual(self._load_text('{"version":1.0}'), Policy())
        self.assertEqual(self._load_text('{"policy":{"fail_under":90}}'), Policy(fail_under=90))

    def test_same_member_names_in_distinct_objects_are_not_duplicates(self):
        items = [
            {"rule": rule, "reason": "Reviewed synthetic fixture.", "expires": "2099-01-01"}
            for rule in ("dead-path", "curl-pipe-shell")
        ]
        policy = self._load_text(json.dumps({"suppressions": items}))
        self.assertEqual(len(policy.suppressions), 2)

    def test_json_like_string_content_is_not_decoded_again(self):
        reason = 'Reviewed literal example: {"field":90,"field":0}; NaN is text here.'
        policy = self._load_text(json.dumps({"suppressions": [{
            "rule": "dead-path", "reason": reason, "expires": "2099-01-01",
        }]}))
        self.assertEqual(policy.suppressions[0].reason, reason)

    def test_missing_configuration_still_uses_compatibility_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_policy(Path(directory)), Policy())

    def test_scan_and_feedback_reject_before_analysis_or_report_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / CONFIG_NAME
            config.write_text(AMBIGUOUS, encoding="utf-8")
            artifact = root / "existing-report"
            artifact.write_bytes(b"preserve this report")
            for args in (
                [str(root), "--json", "--fail-under", "0", "--html", str(artifact)],
                ["feedback", str(root), "--output", str(artifact)],
            ):
                stdout, stderr = io.StringIO(), io.StringIO()
                with self.subTest(args=args), patch("agent_config_score.cli.analyze") as analyze:
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        code = main(args)
                    self.assertEqual(code, 2)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertIn("duplicate JSON member", stderr.getvalue())
                    self.assertNotIn("Traceback", stderr.getvalue())
                    self.assertEqual(artifact.read_bytes(), b"preserve this report")
                    self.assertEqual(config.read_text(encoding="utf-8"), AMBIGUOUS)
                    analyze.assert_not_called()

    def test_compare_rejects_either_invalid_tree_even_with_cli_overrides(self):
        for invalid in ("base", "head"):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                base, head = root / "base", root / "head"
                base.mkdir()
                head.mkdir()
                (root / invalid / CONFIG_NAME).write_text(AMBIGUOUS, encoding="utf-8")
                stdout, stderr = io.StringIO(), io.StringIO()
                with patch("agent_config_score.cli.compare") as compare:
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        code = main(["compare", str(base), str(head), "--json", "--max-drop", "100"])
                    self.assertEqual(code, 2)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertIn("duplicate JSON member", stderr.getvalue())
                    compare.assert_not_called()

    def test_git_diff_rejects_either_invalid_tree_and_cleans_worktree(self):
        for invalid in ("base", "head"):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _git(root, "init", "-q", "--template=")
                hooks = root / "empty-hooks"
                hooks.mkdir()
                _git(root, "config", "core.hooksPath", str(hooks))
                _git(root, "config", "user.name", "ACS Tests")
                _git(root, "config", "user.email", "tests@example.invalid")
                config = root / CONFIG_NAME
                config.write_text(AMBIGUOUS if invalid == "base" else '{}', encoding="utf-8")
                _git(root, "add", CONFIG_NAME)
                _git(root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "baseline")
                config.write_text(AMBIGUOUS if invalid == "head" else '{}', encoding="utf-8")
                before = config.read_bytes()
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = main(["diff", "HEAD", "--path", str(root), "--json"])
                self.assertEqual(code, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("duplicate JSON member", stderr.getvalue())
                self.assertEqual(config.read_bytes(), before)
                worktrees = _git(root, "worktree", "list", "--porcelain")
                self.assertEqual(sum(line.startswith("worktree ") for line in worktrees.splitlines()), 1)

    def test_doctor_reports_structured_config_error_without_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / CONFIG_NAME).write_text(AMBIGUOUS, encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(["doctor", str(root), "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(stderr.getvalue(), "")
            report = json.loads(stdout.getvalue())
            self.assertFalse(report["ok"])
            config = next(check for check in report["checks"] if check["name"] == "config")
            self.assertEqual(config["status"], "error")
            self.assertIn("duplicate JSON member", config["message"])
            self.assertNotIn("schema", [check["name"] for check in report["checks"]])

    def test_doctor_policy_and_schema_are_from_one_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / CONFIG_NAME).write_text(json.dumps({"$schema": SCHEMA_URL}), encoding="utf-8")
            original_read = Path.read_text
            reads = []

            def read_once(path, *args, **kwargs):
                reads.append(path)
                self.assertEqual(len(reads), 1, "Doctor reread the config for schema metadata")
                return original_read(path, *args, **kwargs)

            with patch.object(Path, "read_text", read_once):
                checks, policy = _check_config(root)
            self.assertEqual(policy, Policy())
            self.assertEqual(next(check.status for check in checks if check.name == "schema"), "pass")

    def test_doctor_loader_operational_error_is_structured(self):
        with patch("agent_config_score.doctor._load_policy_document", side_effect=PermissionError("synthetic-private-detail")):
            checks, policy = _check_config(Path("."))
        self.assertIsNone(policy)
        self.assertEqual([(check.name, check.status) for check in checks], [("config", "error")])
        self.assertNotIn("synthetic-private-detail", checks[0].message)


if __name__ == "__main__":
    unittest.main()
