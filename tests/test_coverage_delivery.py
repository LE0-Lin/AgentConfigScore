import contextlib
import importlib.util
import io
import html
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score.entrypoint import main
from agent_config_score.initializer import initialize_repository, InitError
from agent_config_score.scanner import compare_cursor_coverage, cursor_coverage_markdown

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("coverage_adapter", ROOT / "scripts/check_cursor_coverage.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class CoverageDeliveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.base, self.head = self.root / "base", self.root / "head"
        for root, pattern in ((self.base, "src/**"), (self.head, "src/web/**")):
            rules = root / ".cursor/rules"
            rules.mkdir(parents=True)
            (rules / "policy.mdc").write_text(
                f'---\nglobs: "{pattern}"\nalwaysApply: false\n---\nNever delete files without approval.\n', encoding="utf-8")
            (root / "src").mkdir()
            (root / "src/api.py").write_text("private-target-content\n", encoding="utf-8")

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def report(self):
        report = compare_cursor_coverage(self.base, self.head, under=["src"])
        report["review_gate"] = {"failed": True, "reasons": ["recognized_active_directives_lost"],
                                 "fail_on_lost_directives": True, "fail_on_unknown": True}
        return report

    def test_markdown_preserves_failure_and_json_and_excludes_raw_body(self):
        markdown = self.root / "out/review.md"
        code, output, error = self.cli("scope", "coverage", str(self.base), str(self.head), "--under", "src",
                                       "--fail-on-lost-directives", "--json", "--markdown", str(markdown))
        self.assertEqual((code, error), (1, ""))
        self.assertEqual(json.loads(output)["summary"]["files_with_losses"], 1)
        text = markdown.read_text(encoding="utf-8")
        for value in ("Review gate failed", "src/api.py", ".cursor/rules/policy.mdc:5", "rerun", "Inventory boundary"):
            self.assertIn(value, html.unescape(text))
        for private in ("Never delete", "private-target", "src/web/**"):
            self.assertNotIn(private, text)

    def test_markdown_escapes_repository_controlled_paths(self):
        report = self.report()
        value = '<img src=x onerror=alert(1)>|[bad](https://example.invalid)'
        report["contexts"][0]["target"] = value
        text = cursor_coverage_markdown(report)
        self.assertNotIn("<img", text)
        self.assertIn("&lt;img", text)
        self.assertIn("&#124;", text)
        self.assertNotIn("[bad]", text)
        self.assertNotIn("https://", text)

    def test_report_write_failure_emits_no_success_json(self):
        code, output, _ = self.cli("scope", "coverage", str(self.base), str(self.head), "--under", "src",
                                   "--json", "--markdown", str(self.root))
        self.assertEqual((code, output), (2, ""))

    def test_generated_setup_is_read_only_by_default_and_preserves_policy(self):
        repo = self.root / "setup"
        repo.mkdir()
        policy = repo / ".agentconfigscore.json"
        original = b'private-invalid-unselected-policy-\xff'
        policy.write_bytes(original)
        initialize_repository(repo, include_config=False, coverage_under=["src", "tests"])
        self.assertEqual(policy.read_bytes(), original)
        workflow = repo / ".github/workflows/agent-config-score.yml"
        text = workflow.read_text(encoding="utf-8")
        # The public copy-ready recipe and the installed generator share one contract.
        one_prefix = self.root / "one-prefix"
        one_prefix.mkdir()
        initialize_repository(one_prefix, include_config=False, coverage_under=["src"])
        self.assertEqual((one_prefix / ".github/workflows/agent-config-score.yml").read_text(encoding="utf-8"),
                         (ROOT / "examples/cursor-coverage.yml").read_text(encoding="utf-8"))
        for value in ("coverage-under: |", "            src", "            tests", "coverage-exit-code", "upload-artifact@", "!cancelled()"):
            self.assertIn(value, text)
        self.assertNotIn("pull-requests: write", text)
        self.assertNotIn("pull_request_target", text)
        self.assertEqual(initialize_repository(repo, include_config=False, coverage_under=["src", "tests"])[0].action, "unchanged")

    def test_setup_dry_run_conflicts_and_prefix_validation_do_not_write(self):
        repo = self.root / "setup"
        repo.mkdir()
        for prefixes in (["../outside"], ["src/${{ secrets.ANY }}"], []):
            with self.assertRaises(InitError):
                initialize_repository(repo, coverage_under=prefixes)
            self.assertEqual(list(repo.iterdir()), [])
        initialize_repository(repo, coverage_under=["src"], dry_run=True)
        self.assertEqual(list(repo.iterdir()), [])
        with self.assertRaises(InitError):
            initialize_repository(repo, include_workflow=False, coverage_under=["src"])
        workflow = repo / ".github/workflows/agent-config-score.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("custom", encoding="utf-8")
        with self.assertRaises(InitError):
            initialize_repository(repo, coverage_under=["src"])
        self.assertFalse((repo / ".agentconfigscore.json").exists())
        self.assertEqual(workflow.read_text(), "custom")

    def test_coverage_can_combine_with_explicit_comment_setup(self):
        repo = self.root / "setup"
        repo.mkdir()
        initialize_repository(repo, pr_comment=True, coverage_under=["src"])
        text = (repo / ".github/workflows/agent-config-score.yml").read_text(encoding="utf-8")
        self.assertEqual(text.count("id: acs"), 1)
        self.assertIn("head.repo.full_name == github.repository", text)
        self.assertIn("Require configured coverage support", text)

    def adapter_env(self):
        return {"GITHUB_OUTPUT": str(self.root / "outputs"), "GITHUB_STEP_SUMMARY": str(self.root / "summary"),
                "RUNNER_TEMP": str(self.root), "ACS_COVERAGE_UNDER": "src"}

    def test_action_adapter_retains_review_reports_even_on_exit_one(self):
        report = self.report()
        def invoke(args, **kwargs):
            self.assertIn("-I", args)
            Path(args[args.index("--markdown") + 1]).write_text(cursor_coverage_markdown(report), encoding="utf-8")
            return subprocess.CompletedProcess(args, 1, json.dumps(report), "")
        with patch.dict(os.environ, self.adapter_env()), patch.object(adapter.subprocess, "run", side_effect=invoke):
            self.assertEqual(adapter.main(["--base", str(self.base), "--head", str(self.head)]), 1)
        outputs = (self.root / "outputs").read_text()
        self.assertIn("coverage-exit-code=1", outputs)
        self.assertIn("coverage-lost-files=1", outputs)
        path = next(line.split("=", 1)[1] for line in outputs.splitlines() if line.startswith("coverage-json="))
        self.assertEqual(json.loads(Path(path).read_text())["summary"]["files_with_losses"], 1)
        self.assertIn("Review gate failed", (self.root / "summary").read_text())

    def test_adapter_operational_errors_never_export_success_reports(self):
        for result in (subprocess.CompletedProcess([], 2, "", "unreadable"), subprocess.CompletedProcess([], 0, "{}", "")):
            with self.subTest(result=result):
                for name in ("outputs", "summary"):
                    (self.root / name).write_text("", encoding="utf-8")
                with patch.dict(os.environ, self.adapter_env()), patch.object(adapter.subprocess, "run", return_value=result), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(adapter.main(["--base", str(self.base), "--head", str(self.head)]), 2)
                outputs = (self.root / "outputs").read_text()
                self.assertIn("coverage-exit-code=2", outputs)
                self.assertNotIn("coverage-json=", outputs)
                self.assertIn("coverage unavailable", (self.root / "summary").read_text())

    def test_adapter_refuses_a_success_exit_for_a_failed_gate(self):
        report = self.report()
        def invoke(args, **kwargs):
            Path(args[args.index("--markdown") + 1]).write_text("review", encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, json.dumps(report), "")
        with patch.dict(os.environ, self.adapter_env()), patch.object(adapter.subprocess, "run", side_effect=invoke), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(adapter.main(["--base", str(self.base), "--head", str(self.head)]), 2)
        self.assertNotIn("coverage-json=", (self.root / "outputs").read_text())


if __name__ == "__main__":
    unittest.main()
