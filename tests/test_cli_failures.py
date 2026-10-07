import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score.config import ConfigError, load_policy
from agent_config_score.doctor import diagnose
from agent_config_score.entrypoint import main
from agent_config_score.initializer import InitError, initialize_repository


class CliFailureTests(unittest.TestCase):
    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_non_utf8_config_is_a_safe_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            (root / ".agentconfigscore.json").write_bytes(b'{"private":"secret-value-\xff"}')
            with self.assertRaisesRegex(ConfigError, "UTF-8") as caught:
                load_policy(root)
            self.assertNotIn("secret-value", str(caught.exception))
            for args in ([str(root), "--json"], ["feedback", str(root)],
                         ["compare", str(root), str(root), "--json"]):
                with self.subTest(args=args):
                    code, stdout, stderr = self.invoke(args)
                    self.assertEqual(code, 2)
                    self.assertEqual(stdout, "")
                    self.assertIn("UTF-8", stderr)
                    self.assertNotIn("secret-value", stderr)
            code, stdout, stderr = self.invoke(["doctor", str(root), "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            self.assertFalse(json.loads(stdout)["ok"])
            self.assertIn("UTF-8", stdout)
            self.assertNotIn("secret-value", stdout)

    def test_non_utf8_workflow_remains_a_structured_doctor_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github" / "workflows" / "agent-config-score.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_bytes(b"private-workflow-\xff")
            code, stdout, stderr = self.invoke(["doctor", str(root), "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            checks = {item["name"]: item for item in json.loads(stdout)["checks"]}
            self.assertEqual(checks["workflow"]["status"], "error")
            self.assertIn("UTF-8", checks["workflow"]["message"])
            self.assertNotIn("private-workflow", stdout)

    def test_init_does_not_write_a_partial_config_for_non_utf8_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / ".github" / "workflows" / "agent-config-score.yml"
            workflow.parent.mkdir(parents=True)
            original = b"private-workflow-\xff"
            workflow.write_bytes(original)
            with self.assertRaisesRegex(InitError, "UTF-8"):
                initialize_repository(root)
            self.assertFalse((root / ".agentconfigscore.json").exists())
            self.assertEqual(workflow.read_bytes(), original)
            code, stdout, stderr = self.invoke(["init", str(root)])
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("UTF-8", stderr)
            self.assertNotIn("private-workflow", stderr)

    def test_unwritable_outputs_are_operational_errors_not_successful_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            output = root / "a-directory"
            output.mkdir()
            invocations = [[str(root), "--json", option, str(output)]
                           for option in ("--html", "--badge", "--sarif")]
            invocations += [["compare", str(root), str(root), "--json", "--markdown", str(output)],
                            ["feedback", str(root), "--output", str(output)]]
            for args in invocations:
                with self.subTest(args=args):
                    code, stdout, stderr = self.invoke(args)
                    self.assertEqual(code, 2)
                    self.assertEqual(stdout, "")
                    self.assertIn("error:", stderr)
                    self.assertNotIn("Traceback", stderr)

    def test_unreadable_ignore_file_is_not_a_clean_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            (root / ".agentconfigscoreignore").mkdir()
            code, stdout, stderr = self.invoke([str(root), "--json"])
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("error:", stderr)
            report = diagnose(root)
            self.assertFalse(report.ok)
            check = next(item for item in report.checks if item.name == "instructions")
            self.assertEqual(check.status, "error")

    def test_write_permission_failure_has_concise_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            with patch("pathlib.Path.write_text", side_effect=PermissionError(13, "Permission denied")):
                code, stdout, stderr = self.invoke([str(root), "--json", "--html", str(root / "report.html")])
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("Permission denied", stderr)


if __name__ == "__main__":
    unittest.main()
