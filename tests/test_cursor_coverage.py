import contextlib
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score.entrypoint import main
from agent_config_score.provenance import ToolIdentity
from agent_config_score.scanner import compare_cursor_coverage, compare_cursor_scope
from agent_config_score.scopes import ScopeInputError


def mdc(pattern="src/**"):
    return f'---\nglobs: "{pattern}"\nalwaysApply: false\n---\nNever delete files without approval.\n'


class CursorCoverageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.base, self.head = self.root / "base", self.root / "head"
        for root in (self.base, self.head):
            self.write(root, ".cursor/rules/policy.mdc", mdc())
            self.write(root, "src/api/service.py", "private-code-not-read\n")
            self.write(root, "src/web/app.ts", "private-code-not-read\n")

    def write(self, root, rel, text):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def invoke(self, *flags):
        stdout, stderr = io.StringIO(), io.StringIO()
        args = ["scope", "coverage", str(self.base), str(self.head), "--under", "src", *flags]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_single_file_loss_is_not_masked_by_another_matching_file(self):
        self.write(self.head, ".cursor/rules/policy.mdc", mdc("src/web/**"))
        multi = compare_cursor_scope(self.base, self.head, ["src/api/service.py", "src/web/app.ts"])
        self.assertEqual(multi["summary"]["recognized_active_losses"], 0)
        code, output, error = self.invoke("--fail-on-lost-directives", "--fail-on-unknown", "--json")
        self.assertEqual((code, error), (1, ""))
        report = json.loads(output)
        self.assertEqual(report["summary"]["files_with_losses"], 1)
        api, web = report["contexts"]
        self.assertEqual((api["target"], api["recognized_active_losses"]), ("src/api/service.py", 1))
        self.assertEqual(web["retained_active_directives"], 1)
        self.assertEqual(api["lost_directives"][0]["base"]["sources"][0]["line"], 5)
        self.assertEqual(report["sources"]["head"][0]["metadata_lines"]["globs"], 2)
        self.assertFalse(report["observed_agent_context"])
        for private in ("private-code", "Never delete", "src/web/**"):
            self.assertNotIn(private, output)

    def test_repair_and_unchanged_controls_pass(self):
        for pattern in ("src/**", "src/api/**, src/web/**"):
            self.write(self.head, ".cursor/rules/policy.mdc", mdc(pattern))
            code, output, error = self.invoke("--fail-on-lost-directives", "--fail-on-unknown", "--json")
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(json.loads(output)["summary"]["files_with_losses"], 0)

    def test_rule_rename_and_another_active_copy_retain_directives(self):
        rule = self.head / ".cursor/rules/policy.mdc"
        rule.rename(rule.with_name("renamed.mdc"))
        self.assertEqual(self.invoke("--fail-on-lost-directives")[0], 0)
        self.write(self.head, ".cursor/rules/renamed.mdc", mdc("src/web/**"))
        self.write(self.head, ".cursor/rules/api.mdc", mdc("src/api/**"))
        result = compare_cursor_coverage(self.base, self.head, under=["src"])
        self.assertEqual(result["summary"]["files_with_losses"], 0)
        self.assertEqual(result["contexts"][0]["automatic_attachment_losses"], [".cursor/rules/policy.mdc"])

    def test_unknown_activation_is_not_a_definite_loss(self):
        self.write(self.head, ".cursor/rules/policy.mdc", "---\nalwaysApply: false\n---\nNever delete files without approval.\n")
        code, output, _ = self.invoke("--fail-on-lost-directives", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["summary"]["files_with_unknown"], 2)
        code, output, _ = self.invoke("--fail-on-lost-directives", "--fail-on-unknown", "--json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output)["review_gate"]["reasons"], ["unknown_scope_or_body"])

    def test_opaque_candidate_body_stays_unknown(self):
        self.write(self.head, ".cursor/rules/policy.mdc", mdc().replace(
            "Never delete files without approval.", "<policy>Never delete files without approval.</policy>"))
        result = compare_cursor_coverage(self.base, self.head, under=["src"])
        self.assertEqual(result["summary"]["recognized_active_losses"], 0)
        self.assertEqual(result["summary"]["files_with_unknown"], 2)

    def test_capture_reads_each_rule_once_and_never_reads_target_contents(self):
        sources = {root / ".cursor/rules/policy.mdc" for root in (self.base, self.head)}
        reads = {path: 0 for path in sources}
        original = Path.read_text

        def read(path, *args, **kwargs):
            if path.is_relative_to(self.root):
                self.assertIn(path, sources, "Read a target's contents instead of its name")
                reads[path] += 1
                self.assertEqual(reads[path], 1, "Reopened a captured source")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", read):
            first = compare_cursor_coverage(self.base, self.head, under=["src"])
        self.assertEqual(set(reads.values()), {1})
        self.assertEqual(first, compare_cursor_coverage(self.base, self.head, under=["src"]))

    def test_union_keeps_added_and_deleted_target_names(self):
        (self.head / "src/api/service.py").unlink()
        self.write(self.head, "src/new.py", "")
        self.write(self.head, "src-other/not-selected.py", "")
        result = compare_cursor_coverage(self.base, self.head, under=["src/", "src\\api"])
        rows = {row["target"]: row for row in result["contexts"]}
        self.assertEqual(set(rows), {"src/api/service.py", "src/new.py", "src/web/app.ts"})
        self.assertFalse(rows["src/api/service.py"]["present_in_head"])
        self.assertFalse(rows["src/new.py"]["present_in_base"])

    def test_empty_inventory_and_invalid_prefixes_cannot_pass(self):
        self.assertEqual(self.invoke("--under", "missing", "--json")[0], 0)  # src still selected
        with self.assertRaises(ScopeInputError):
            compare_cursor_coverage(self.base, self.head, under=["missing"])
        for prefix in ("../outside", "C:/outside", "/outside"):
            with patch("agent_config_score.scanner._capture_cursor_scope", side_effect=AssertionError("Read before validation")):
                with self.assertRaises(ScopeInputError):
                    compare_cursor_coverage(self.base, self.head, under=[prefix])

    def test_resource_limits_fail_instead_of_truncating_inventory(self):
        with patch("agent_config_score.scanner.MAX_COVERAGE_FILES", 1):
            self.assertEqual(self.invoke("--json")[:2], (2, ""))
        with patch("agent_config_score.scanner.MAX_COVERAGE_UNITS", 0):
            self.assertEqual(self.invoke("--json")[:2], (2, ""))
        self.write(self.base, "src/only-base.py", "")
        self.write(self.head, "src/only-head.py", "")
        with patch("agent_config_score.scanner.MAX_COVERAGE_FILES", 3):
            self.assertEqual(self.invoke("--json")[:2], (2, ""))

    def test_io_failures_emit_no_partial_report_or_raw_path(self):
        private = "private-system-path"
        with patch("agent_config_score.scanner._cursor_coverage_inventory", side_effect=OSError(errno.EACCES, private)):
            code, output, error = self.invoke("--json")
        self.assertEqual((code, output), (2, ""))
        self.assertNotIn(private, error)
        (self.head / ".cursor/rules/policy.mdc").write_bytes(b"private-invalid-utf8-\xff")
        self.assertEqual(self.invoke("--json")[:2], (2, ""))

    def test_runtime_identity_mismatch_aborts(self):
        with patch("agent_config_score.scanner.capture_tool_identity", side_effect=[
            ToolIdentity("0.24.0", "a" * 64), ToolIdentity("0.24.0", "b" * 64)
        ]):
            self.assertEqual(self.invoke("--json")[:2], (2, ""))

    def test_inventory_excludes_dependency_trees_and_file_aliases(self):
        self.write(self.base, "src/node_modules/pkg/private.py", "")
        self.write(self.base, "src/.git/private", "")
        alias = self.base / "src/alias.py"
        try:
            alias.symlink_to(self.base / "src/api/service.py")
        except OSError:
            self.skipTest("File symlink creation unavailable")
        result = compare_cursor_coverage(self.base, self.head, under=["src"])
        excluded = result["file_inventory"]["base"]["excluded"]
        self.assertEqual(excluded["file_aliases"], 1)
        self.assertEqual(excluded["dependency_admin_directories"], 2)
        self.assertEqual(result["summary"]["files"], 2)

    def test_zero_recognized_baseline_coverage_is_visible(self):
        for root in (self.base, self.head):
            (root / ".cursor/rules/policy.mdc").unlink()
        report = compare_cursor_coverage(self.base, self.head, under=["src"])
        self.assertEqual(report["summary"]["baseline_covered_files"], 0)
        self.assertEqual(report["summary"]["files_without_recognized_baseline"], 2)

    @unittest.skipIf(os.name == "nt", "Backslash is a native separator on Windows")
    def test_nonportable_literal_backslash_cannot_relabel_an_actual_file(self):
        self.write(self.head, "src/literal\\name.py", "")
        self.assertEqual(self.invoke("--json")[:2], (2, ""))

    def test_cli_rejects_ambiguous_modes_before_creating_worktrees(self):
        for args in (["scope", "coverage"],
                     ["scope", "coverage", "base", "head", "--base-ref", "HEAD"],
                     ["scope", "coverage", "base", "head", "--path", "."]):
            with contextlib.redirect_stderr(io.StringIO()), patch(
                "agent_config_score.cli.baseline_worktree", side_effect=AssertionError("Created a worktree")
            ):
                with self.assertRaises(SystemExit) as raised:
                    main(args)
            self.assertEqual(raised.exception.code, 2)

    def test_git_mode_pins_baseline_and_cleans_up_on_success_and_failure(self):
        def git(*args):
            process = subprocess.run(["git", "-C", str(self.base), *args], capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            return process.stdout.strip()

        git("init", "-q", "-b", "main", "--template=")
        hooks = self.root / "empty-hooks"
        hooks.mkdir()
        for key, value in (("core.hooksPath", str(hooks)), ("commit.gpgsign", "false"),
                           ("user.name", "Coverage Test"), ("user.email", "coverage@example.invalid")):
            git("config", key, value)
        git("add", ".")
        git("-c", "core.autocrlf=false", "commit", "-qm", "baseline")
        sha = git("rev-parse", "HEAD")
        rule = self.write(self.base, ".cursor/rules/policy.mdc", mdc("src/web/**"))
        args = ["scope", "coverage", "--base-ref", "HEAD", "--path", str(self.base), "--under", "src",
                "--fail-on-lost-directives", "--json"]
        for bad_source in (False, True):
            if bad_source:
                rule.write_bytes(b"\xff")
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(args)
            if bad_source:
                self.assertEqual((code, stdout.getvalue()), (2, ""))
            else:
                self.assertEqual(code, 1, stderr.getvalue())
                self.assertEqual(json.loads(stdout.getvalue())["comparison_inputs"]["base_commit"], sha)
            self.assertEqual(sum(line.startswith("worktree ") for line in git("worktree", "list", "--porcelain").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
