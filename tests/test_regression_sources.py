import contextlib
from dataclasses import asdict
from datetime import date
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score.config import Suppression
from agent_config_score.entrypoint import main
from agent_config_score.regression import compare
from agent_config_score.scanner import analyze


class RegressionFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name).resolve()
        self.base = self.workspace / "base"
        self.head = self.workspace / "head"
        self.base.mkdir()
        self.head.mkdir()

    def write(self, root, files):
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def removed(self, report):
        return [finding.file for finding in report.new_findings if finding.code == "instruction-file-removed"]

    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()


class RegressionCaptureTests(RegressionFixture):
    def test_each_source_is_read_once_and_flip_is_not_lost_to_a_later_read_error(self):
        self.write(self.base, {"AGENTS.md": "Always run tests.\n"})
        self.write(self.head, {"AGENTS.md": "Never run tests.\n"})
        sources = {self.base / "AGENTS.md": 0, self.head / "AGENTS.md": 0}
        original = Path.read_text

        def read_once(path, *args, **kwargs):
            if path in sources:
                sources[path] += 1
                if sources[path] > 1:
                    raise PermissionError("unavailable after capture")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", new=read_once):
            report = compare(self.base, self.head)
        self.assertIn("directive-polarity-flip", [finding.code for finding in report.new_errors])
        self.assertEqual(list(sources.values()), [1, 1])

    def test_cli_preserves_flip_and_fails_enabled_new_error_gate_without_rereading(self):
        self.write(self.base, {"AGENTS.md": "Always run tests.\n"})
        self.write(self.head, {"AGENTS.md": "Never run tests.\n"})
        sources = {self.base / "AGENTS.md": 0, self.head / "AGENTS.md": 0}
        original = Path.read_text

        def read_once(path, *args, **kwargs):
            if path in sources:
                sources[path] += 1
                if sources[path] > 1:
                    raise OSError("unavailable after capture")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", new=read_once):
            code, stdout, stderr = self.invoke([
                "compare", str(self.base), str(self.head), "--json", "--fail-on-new-errors",
            ])
        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertIn("directive-polarity-flip", [f["code"] for f in json.loads(stdout)["new_findings"]])

    def test_later_text_replacement_cannot_rewrite_the_captured_polarity(self):
        self.write(self.base, {"AGENTS.md": "Always run tests.\n"})
        self.write(self.head, {"AGENTS.md": "Never run tests.\n"})
        source = self.head / "AGENTS.md"
        original = Path.read_text
        reads = 0

        def replace_after_read(path, *args, **kwargs):
            nonlocal reads
            text = original(path, *args, **kwargs)
            if path == source:
                reads += 1
                if reads == 1:
                    source.write_text("Always run tests.\n", encoding="utf-8")
            return text

        with patch.object(Path, "read_text", new=replace_after_read):
            report = compare(self.base, self.head)
        self.assertIn("directive-polarity-flip", [finding.code for finding in report.new_errors])
        self.assertEqual(reads, 1)

    def test_deletion_after_capture_is_not_an_invented_removed_file(self):
        self.write(self.base, {"AGENTS.md": "Always run tests.\n"})
        self.write(self.head, {"AGENTS.md": "Always run tests.\n"})
        source = self.head / "AGENTS.md"
        original = Path.read_text

        def delete_after_read(path, *args, **kwargs):
            text = original(path, *args, **kwargs)
            if path == source:
                source.unlink()
            return text

        with patch.object(Path, "read_text", new=delete_after_read):
            report = compare(self.base, self.head)
        self.assertEqual(report.new_findings, [])
        self.assertEqual(report.head.files, ["AGENTS.md"])
        self.assertFalse(source.exists())

    def test_external_alias_installed_after_capture_is_not_opened(self):
        self.write(self.base, {"AGENTS.md": "Always run tests.\n"})
        self.write(self.head, {"AGENTS.md": "Never run tests.\n"})
        source = self.head / "AGENTS.md"
        outside = self.workspace / "private.txt"
        outside.write_text("private external sentinel\n", encoding="utf-8")
        original = Path.read_text
        reads = 0

        def replace_after_read(path, *args, **kwargs):
            nonlocal reads
            if path == source:
                reads += 1
                if reads > 1:
                    raise AssertionError("unsafe second read of replaced alias")
            text = original(path, *args, **kwargs)
            if path == source:
                source.unlink()
                try:
                    os.symlink(outside, source)
                except OSError:
                    self.skipTest("host does not permit symbolic links")
            return text

        with patch.object(Path, "read_text", new=replace_after_read):
            report = compare(self.base, self.head)
        self.assertEqual(reads, 1)
        self.assertIn("directive-polarity-flip", [finding.code for finding in report.new_errors])
        self.assertNotIn("private external sentinel", json.dumps(report.to_dict()))

    def test_first_read_failure_is_still_an_operational_failure_without_artifacts(self):
        self.write(self.base, {"AGENTS.md": "Always run tests.\n"})
        self.write(self.head, {"AGENTS.md": "Never run tests.\n"})
        original = Path.read_text

        def unreadable(path, *args, **kwargs):
            if path == self.head / "AGENTS.md":
                raise PermissionError("private error detail")
            return original(path, *args, **kwargs)

        output = self.workspace / "comparison.md"
        with patch.object(Path, "read_text", new=unreadable):
            code, stdout, stderr = self.invoke([
                "compare", str(self.base), str(self.head), "--json", "--markdown", str(output),
            ])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertNotIn("private error detail", stderr)
        self.assertFalse(output.exists())

    def test_public_reports_do_not_retain_or_export_raw_source_text(self):
        private_text = "private source sentinel without a matching directive\n"
        self.write(self.base, {"AGENTS.md": private_text})
        self.write(self.head, {"AGENTS.md": private_text})
        reports = [analyze(self.base), compare(self.base, self.head)]
        for report in reports:
            with self.subTest(type=type(report).__name__):
                self.assertNotIn(private_text.strip(), repr(report))
                self.assertNotIn(private_text.strip(), json.dumps(asdict(report)))
                self.assertNotIn(private_text.strip(), json.dumps(report.to_dict()))


class InstructionMoveTests(RegressionFixture):
    TEXT = "Always run tests before merging.\n"

    def test_existing_duplicate_does_not_hide_an_actual_deletion(self):
        self.write(self.base, {"AGENTS.md": self.TEXT, "CLAUDE.md": self.TEXT})
        self.write(self.head, {"AGENTS.md": self.TEXT})
        self.assertEqual(self.removed(compare(self.base, self.head)), ["CLAUDE.md"])

    def test_one_new_target_cannot_exempt_two_removed_sources(self):
        self.write(self.base, {"CLAUDE.md": self.TEXT, "GEMINI.md": self.TEXT})
        self.write(self.head, {"AGENTS.md": self.TEXT})
        report = compare(self.base, self.head)
        self.assertEqual(len(self.removed(report)), 1)

    def test_two_new_targets_can_match_two_removed_sources(self):
        self.write(self.base, {"CLAUDE.md": self.TEXT, "GEMINI.md": self.TEXT})
        self.write(self.head, {"AGENTS.md": self.TEXT, ".cursorrules": self.TEXT})
        self.assertEqual(self.removed(compare(self.base, self.head)), [])

    def test_root_rules_moved_to_a_subdirectory_still_need_removal_review(self):
        self.write(self.base, {"AGENTS.md": self.TEXT})
        self.write(self.head, {"packages/client/AGENTS.md": self.TEXT})
        self.assertEqual(self.removed(compare(self.base, self.head)), ["AGENTS.md"])

    def test_nested_rules_moved_to_root_still_need_removal_review(self):
        self.write(self.base, {"packages/client/AGENTS.md": self.TEXT})
        self.write(self.head, {"AGENTS.md": self.TEXT})
        self.assertEqual(self.removed(compare(self.base, self.head)), ["packages/client/AGENTS.md"])

    def test_sibling_directory_move_does_not_hide_scope_change(self):
        self.write(self.base, {"packages/old/AGENTS.md": self.TEXT})
        self.write(self.head, {"packages/new/AGENTS.md": self.TEXT})
        self.assertEqual(self.removed(compare(self.base, self.head)), ["packages/old/AGENTS.md"])

    def test_same_directory_exact_text_move_remains_compatible(self):
        self.write(self.base, {"packages/client/CLAUDE.md": self.TEXT})
        self.write(self.head, {"packages/client/AGENTS.md": self.TEXT})
        self.assertEqual(self.removed(compare(self.base, self.head)), [])

    def test_whitespace_inside_literal_text_is_not_erased_for_move_matching(self):
        self.write(self.base, {"CLAUDE.md": 'Use this output:\n\n```text\na  b\n```\n'})
        self.write(self.head, {"AGENTS.md": 'Use this output:\n\n```text\na b\n```\n'})
        self.assertEqual(self.removed(compare(self.base, self.head)), ["CLAUDE.md"])

    def test_line_endings_alone_do_not_prevent_an_exact_text_move(self):
        (self.base / "CLAUDE.md").write_bytes(self.TEXT.replace("\n", "\r\n").encode("utf-8"))
        (self.head / "AGENTS.md").write_bytes(self.TEXT.encode("utf-8"))
        self.assertEqual(self.removed(compare(self.base, self.head)), [])

    def test_empty_new_file_cannot_exempt_an_empty_removed_source(self):
        self.write(self.base, {"CLAUDE.md": ""})
        self.write(self.head, {"AGENTS.md": ""})
        self.assertEqual(self.removed(compare(self.base, self.head)), ["CLAUDE.md"])

    def test_copying_into_a_modified_existing_file_is_not_an_exact_file_move(self):
        self.write(self.base, {"CLAUDE.md": self.TEXT, "AGENTS.md": "Keep changes small.\n"})
        self.write(self.head, {"AGENTS.md": self.TEXT})
        self.assertEqual(self.removed(compare(self.base, self.head)), ["CLAUDE.md"])

    def test_cli_new_error_gate_rejects_scope_change_despite_unchanged_high_scores(self):
        self.write(self.base, {"AGENTS.md": self.TEXT})
        self.write(self.head, {"packages/client/AGENTS.md": self.TEXT})
        code, stdout, stderr = self.invoke([
            "compare", str(self.base), str(self.head), "--json", "--fail-on-new-errors",
        ])
        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        data = json.loads(stdout)
        self.assertEqual((data["base"]["score"], data["head"]["score"], data["delta"]), (100, 100, 0))
        self.assertIn("instruction-file-removed", [f["code"] for f in data["new_findings"]])

    def test_score_only_cli_policy_is_not_silently_changed(self):
        self.write(self.base, {"AGENTS.md": self.TEXT})
        self.write(self.head, {"packages/client/AGENTS.md": self.TEXT})
        code, stdout, stderr = self.invoke(["compare", str(self.base), str(self.head), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("instruction-file-removed", [f["code"] for f in json.loads(stdout)["new_findings"]])

    def test_baseline_owned_path_scoped_exception_remains_auditable(self):
        self.write(self.base, {"AGENTS.md": self.TEXT})
        self.write(self.head, {"packages/client/AGENTS.md": self.TEXT})
        suppression = Suppression("instruction-file-removed", "Reviewed directory migration", date(2099, 1, 1), ("AGENTS.md",))
        report = compare(self.base, self.head, suppressions=(suppression,))
        self.assertEqual(self.removed(report), [])
        self.assertEqual(
            [(item.finding.code, item.finding.file) for item in report.head.suppressed_findings],
            [("instruction-file-removed", "AGENTS.md")],
        )

    def test_candidate_cannot_grant_its_own_scope_migration_exception(self):
        baseline = {"version": 1, "policy": {"fail_on_new_errors": True}}
        candidate = {
            "version": 1, "policy": {"fail_on_new_errors": False},
            "suppressions": [{
                "rule": "instruction-file-removed", "reason": "Candidate migration exception",
                "expires": "2099-01-01", "paths": ["AGENTS.md"],
            }],
        }
        self.write(self.base, {"AGENTS.md": self.TEXT, ".agentconfigscore.json": json.dumps(baseline)})
        self.write(self.head, {"packages/client/AGENTS.md": self.TEXT, ".agentconfigscore.json": json.dumps(candidate)})
        code, stdout, stderr = self.invoke(["compare", str(self.base), str(self.head), "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        data = json.loads(stdout)
        self.assertIn("instruction-file-removed", [f["code"] for f in data["new_findings"]])
        self.assertEqual(data["head"]["suppressed_findings"], [])


if __name__ == "__main__":
    unittest.main()
