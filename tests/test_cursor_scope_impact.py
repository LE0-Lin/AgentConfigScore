import contextlib
import errno
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score.entrypoint import main
from agent_config_score.provenance import ToolIdentity
from agent_config_score.regression import compare
from agent_config_score.scanner import analyze, compare_cursor_scope


def mdc(pattern="src/**", body="Never use tabs.\n"):
    return f'---\nglobs: "{pattern}"\nalwaysApply: false\n---\n{body}'


class CursorScopeImpactTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.base, self.head = self.root / "baseline", self.root / "candidate"
        self.base.mkdir()
        self.head.mkdir()

    def write(self, root, name="policy.mdc", text=None):
        path = root / ".cursor" / "rules" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(mdc() if text is None else text, encoding="utf-8")
        return path

    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def command(self, *flags):
        return ["scope", "compare", str(self.base), str(self.head), "--target", "src/api/a.py", *flags]

    def test_glob_narrowing_loses_activation_while_old_scores_and_gate_are_equal(self):
        self.write(self.base)
        self.write(self.head, text=mdc("src/web/**"))
        result = compare_cursor_scope(self.base, self.head, ["src/api/a.py"])
        self.assertEqual([analyze(root).score for root in (self.base, self.head)], [100, 100])
        self.assertEqual(compare(self.base, self.head).new_errors, [])
        self.assertEqual(result["summary"]["recognized_active_losses"], 1)
        change = result["rule_changes"][0]
        self.assertEqual(change["transition"], "active_to_inactive")
        self.assertEqual(change["trigger_targets_lost"], ["src/api/a.py"])
        self.assertEqual(change["head"]["metadata_lines"]["globs"], 2)
        directive = result["directive_changes"][0]
        self.assertEqual(directive["transition"], "active_to_inactive")
        self.assertEqual(directive["base"]["sources"][0]["line"], 5)
        self.assertEqual(directive["head"]["sources"][0]["activation"], "inactive")
        self.assertFalse(result["scored"])
        self.assertFalse(result["observed_agent_context"])

    def test_multi_file_context_retains_instruction_despite_lost_trigger_match(self):
        self.write(self.base)
        self.write(self.head, text=mdc("src/web/**"))
        result = compare_cursor_scope(self.base, self.head, ["src/api/a.py", "src/web/app.ts"])
        self.assertEqual(result["rule_changes"][0]["trigger_targets_lost"], ["src/api/a.py"])
        self.assertEqual(result["summary"]["automatic_attachment_losses"], 0)
        self.assertEqual(result["summary"]["recognized_active_losses"], 0)
        self.assertEqual(result["summary"]["retained_active_directives"], 1)

    def test_rename_preserves_directive_while_file_removal_stays_visible(self):
        self.write(self.base, "old.mdc")
        self.write(self.head, "renamed.mdc")
        result = compare_cursor_scope(self.base, self.head, ["src/a"])
        self.assertEqual(result["summary"]["rules_removed"], 1)
        self.assertEqual(result["summary"]["rules_added"], 1)
        self.assertEqual(result["summary"]["automatic_attachment_losses"], 1)
        self.assertEqual(result["summary"]["recognized_active_losses"], 0)
        self.assertEqual(result["directive_changes"][0]["transition"], "active_to_active")
        self.assertEqual(self.invoke(self.command("--fail-on-lost-directives", "--fail-on-unknown"))[0], 0)

    def test_another_active_copy_retains_directive_but_inactive_copy_does_not(self):
        self.write(self.base, "old.mdc")
        path = self.write(self.head, "copy.mdc", mdc("docs/**"))
        result = compare_cursor_scope(self.base, self.head, ["src/a"])
        self.assertEqual(result["summary"]["recognized_active_losses"], 1)
        path.write_text(mdc(), encoding="utf-8")
        self.assertEqual(compare_cursor_scope(self.base, self.head, ["src/a"])["summary"]["recognized_active_losses"], 0)

    def test_manual_model_selected_and_unsupported_rules_are_uncertain_not_definite_loss(self):
        self.write(self.base)
        for header in ("alwaysApply: false", "description: Review code\nalwaysApply: false",
                       'globs: "{src,lib}/**"\nalwaysApply: false'):
            with self.subTest(header=header):
                self.write(self.head, text="---\n" + header + "\n---\nNever use tabs.\n")
                result = compare_cursor_scope(self.base, self.head, ["src/api/a.py"])
                self.assertEqual(result["summary"]["recognized_active_losses"], 0)
                self.assertEqual(result["directive_changes"][0]["transition"], "active_to_unknown")
                code, stdout, stderr = self.invoke(self.command("--fail-on-lost-directives", "--fail-on-unknown", "--json"))
                self.assertEqual((code, stderr), (1, ""))
                self.assertEqual(json.loads(stdout)["review_gate"]["reasons"], ["unknown_scope_or_body"])

    def test_uninterpreted_candidate_can_hide_a_replacement_and_remains_unknown(self):
        self.write(self.base)
        for text in ("---\nalwaysApply: true\nNever use tabs.\n",
                     "---\nalwaysApply: true\n---\n<policy>Never use tabs.</policy>\n",
                     "---\nalwaysApply: true\n---\n## Examples\nNever use tabs.\n"):
            with self.subTest(text=text):
                self.write(self.head, text=text)
                result = compare_cursor_scope(self.base, self.head, ["src/a"])
                self.assertEqual(result["summary"]["recognized_active_losses"], 0)
                self.assertEqual(result["summary"]["uninterpreted_noninactive_bodies"], 1)
                self.assertEqual(result["directive_changes"][0]["head"]["availability"], "unknown")

    def test_unknown_baseline_is_not_invented_as_a_protected_active_directive(self):
        self.write(self.base, text="---\nalwaysApply: false\n---\nNever use tabs.\n")
        result = compare_cursor_scope(self.base, self.head, ["src/a"])
        self.assertEqual(result["summary"]["baseline_active_directives"], 0)
        self.assertEqual(result["summary"]["recognized_active_losses"], 0)
        self.assertEqual(self.invoke(self.command("--fail-on-unknown"))[0], 1)

    def test_ignored_md_and_closed_examples_do_not_preserve_active_directive(self):
        self.write(self.base)
        self.write(self.head, "example.md", "Never use tabs.\n")
        self.write(self.head, text=mdc(body="## Examples\nNever use tabs.\n## Policy\nReview the change.\n"))
        result = compare_cursor_scope(self.base, self.head, ["src/a"])
        self.assertEqual(result["summary"]["recognized_active_losses"], 1)
        self.assertFalse(result["summary"]["has_unknown"])

    def test_polarity_reversal_loses_one_exact_directive_and_adds_the_other(self):
        self.write(self.base)
        self.write(self.head, text=mdc(body="Always use tabs.\n"))
        result = compare_cursor_scope(self.base, self.head, ["src/a"])
        self.assertEqual(result["summary"]["recognized_active_losses"], 1)
        self.assertEqual(result["summary"]["recognized_active_gains"], 1)
        self.assertEqual(len({r["directive_sha256"] for r in result["directive_changes"]}), 1)

    def test_paraphrase_requires_review_instead_of_assumed_semantic_equivalence(self):
        self.write(self.base)
        self.write(self.head, text=mdc(body="Always indent with spaces.\n"))
        self.assertEqual(self.invoke(self.command("--fail-on-lost-directives"))[0], 1)
        self.assertEqual(compare_cursor_scope(self.base, self.head, ["src/a"])["summary"]["recognized_active_losses"], 1)

    def test_addition_and_empty_profile_do_not_invent_a_baseline_guarantee(self):
        code, stdout, _ = self.invoke(self.command("--fail-on-lost-directives", "--fail-on-unknown"))
        self.assertEqual(code, 0)
        self.assertIn("no recognized active directives", stdout)
        self.write(self.head)
        result = compare_cursor_scope(self.base, self.head, ["src/a"])
        self.assertEqual(result["summary"]["baseline_active_directives"], 0)
        self.assertEqual(result["summary"]["recognized_active_gains"], 1)

    def test_line_shifts_and_format_changes_preserve_recognition_with_original_evidence(self):
        self.write(self.base)
        self.write(self.head, text=mdc(body="\n# Policy\nNever use tabs.\n"))
        result = compare_cursor_scope(self.base, self.head, ["src/a"])
        change = result["directive_changes"][0]
        self.assertEqual((change["base"]["sources"][0]["line"], change["head"]["sources"][0]["line"]), (5, 7))
        self.assertEqual(change["transition"], "active_to_active")
        self.assertEqual(result["summary"]["recognized_active_losses"], 0)

    def test_each_source_is_captured_once_for_both_attachment_and_directive_evidence(self):
        sources = {self.write(self.base), self.write(self.head, text=mdc("docs/**"))}
        reads = {path: 0 for path in sources}
        original = Path.read_text

        def once(path, *args, **kwargs):
            if path in sources:
                reads[path] += 1
                self.assertEqual(reads[path], 1, "Source reopened after capture")
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", once):
            result = compare_cursor_scope(self.base, self.head, ["src/a"])
        self.assertEqual(set(reads.values()), {1})
        self.assertEqual(result["summary"]["recognized_active_losses"], 1)

    def test_reports_omit_raw_metadata_and_directives_and_are_deterministic(self):
        for root, pattern in ((self.base, "src/**"), (self.head, "private-pattern/**")):
            self.write(root, "z.mdc", mdc(pattern, "Never expose private-instruction-value.\n"))
            self.write(root, "a.mdc", mdc(pattern, "Always use private-format-value.\n"))
        first = compare_cursor_scope(self.base, self.head, ["src/b", "./src/a", "src/a"])
        second = compare_cursor_scope(self.base, self.head, ["src/a", "src/b"])
        self.assertEqual(first, second)
        encoded = json.dumps(first)
        for literal in ("private-pattern", "private-instruction-value", "private-format-value", str(self.root)):
            self.assertNotIn(literal, encoded)
        self.assertEqual([row["file"] for row in first["rule_changes"]], [".cursor/rules/a.mdc", ".cursor/rules/z.mdc"])

    def test_cli_is_advisory_by_default_and_strict_only_when_requested(self):
        self.write(self.base)
        self.write(self.head, text=mdc("docs/**"))
        code, stdout, stderr = self.invoke(self.command("--json"))
        self.assertEqual((code, stderr), (0, ""))
        self.assertFalse(json.loads(stdout)["review_gate"]["failed"])
        code, stdout, stderr = self.invoke(self.command("--fail-on-lost-directives", "--json"))
        self.assertEqual((code, stderr), (1, ""))
        self.assertTrue(json.loads(stdout)["review_gate"]["failed"])
        code, stdout, _ = self.invoke(self.command("--fail-on-lost-directives"))
        self.assertEqual(code, 1)
        self.assertIn("metadata lines [globs:2", stdout)
        self.assertIn("policy.mdc:5", stdout)

    def test_candidate_policy_does_not_change_explicit_scope_gate_and_ignore_removal_is_visible(self):
        self.write(self.base)
        self.write(self.head)
        (self.head / ".agentconfigscoreignore").write_text(".cursor/rules/policy.mdc\n", encoding="utf-8")
        (self.head / ".agentconfigscore.json").write_text('{"policy":{"fail_on_new_errors":false,"fail_under":0}}', encoding="utf-8")
        code, stdout, stderr = self.invoke(self.command("--fail-on-lost-directives", "--json"))
        self.assertEqual((code, stderr), (1, ""))
        result = json.loads(stdout)
        self.assertEqual(result["summary"]["recognized_active_losses"], 1)
        self.assertEqual(result["directive_changes"][0]["transition"], "active_to_not_recognized")

    def test_invalid_paths_fail_before_any_snapshot_or_git_worktree(self):
        with patch("agent_config_score.scanner._cursor_scope_snapshot", side_effect=AssertionError("snapshot read")):
            with self.assertRaises(ValueError):
                compare_cursor_scope(self.base, self.head, ["../outside"])
        with patch("agent_config_score.cli.repository_root", side_effect=AssertionError("Git lookup")):
            code, stdout, _ = self.invoke(["scope", "diff", "HEAD", "--target", "../outside", "--json"])
        self.assertEqual((code, stdout), (2, ""))

    def test_bad_sources_in_either_tree_do_not_emit_partial_success(self):
        for root in (self.base, self.head):
            with self.subTest(side=root.name):
                self.write(self.base)
                self.write(self.head)
                source = self.write(root)
                source.write_bytes(b"private-source-detail-\xff")
                code, stdout, stderr = self.invoke(self.command("--json"))
                self.assertEqual((code, stdout), (2, ""))
                self.assertNotIn("private-source-detail", stderr)
        code, stdout, _ = self.invoke(["scope", "compare", str(self.root / "absent"), str(self.head), "--target", "src/a", "--json"])
        self.assertEqual((code, stdout), (2, ""))

    def test_runtime_identity_change_aborts_instead_of_comparing_different_tools(self):
        with patch("agent_config_score.scanner.capture_tool_identity", side_effect=[ToolIdentity("0.24.0", "a" * 64),
                                                                                   ToolIdentity("0.24.0", "b" * 64)]):
            with self.assertRaises(OSError) as raised:
                compare_cursor_scope(self.base, self.head, ["src/a"])
        self.assertEqual(raised.exception.errno, errno.EAGAIN)

    def test_git_working_tree_comparison_retains_commit_and_cleans_up_on_success_and_error(self):
        def git(*args):
            process = subprocess.run(["git", "-C", str(self.base), *args], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(process.returncode, 0, process.stderr)
            return process.stdout.strip()

        git("init", "-q", "-b", "main", "--template=")
        hooks = self.root / "empty-hooks"
        hooks.mkdir()
        for key, value in (("core.hooksPath", str(hooks)), ("user.name", "Scope Test"),
                           ("user.email", "scope@example.invalid"), ("commit.gpgsign", "false")):
            git("config", key, value)
        source = self.write(self.base)
        git("add", ".")
        git("-c", "core.autocrlf=false", "commit", "-qm", "baseline")
        sha = git("rev-parse", "HEAD")
        source.write_text(mdc("docs/**"), encoding="utf-8")
        before = source.read_bytes()
        args = ["scope", "diff", "HEAD", "--path", str(self.base), "--target", "src/api/a.py", "--fail-on-lost-directives", "--json"]
        code, stdout, stderr = self.invoke(args)
        self.assertEqual((code, stderr), (1, ""))
        result = json.loads(stdout)
        self.assertEqual(result["comparison_inputs"]["base_commit"], sha)
        self.assertEqual(result["comparison_inputs"]["head"], "working_tree")
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(sum(line.startswith("worktree ") for line in git("worktree", "list", "--porcelain").splitlines()), 1)
        auto_args = [arg for index, arg in enumerate(args) if index != 2]
        self.assertEqual(json.loads(self.invoke(auto_args)[1])["comparison_inputs"]["base_ref"], "main")
        for candidate in (["scope", "diff", "missing-ref", "--path", str(self.base), "--target", "src/a", "--json"], args):
            if candidate is args:
                source.write_bytes(b"\xff")
            code, stdout, _ = self.invoke(candidate)
            self.assertEqual((code, stdout), (2, ""))
            self.assertEqual(sum(line.startswith("worktree ") for line in git("worktree", "list", "--porcelain").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
