import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score import guardrails
from agent_config_score.entrypoint import main
from agent_config_score.scanner import _deletion_guardrail_evidence, analyze


class GuardrailRecognitionTests(unittest.TestCase):
    def test_explicit_supported_constraints_are_recognized_without_literal_rm(self):
        cases = [
            "Before deleting files, ask for confirmation.",
            "Always ask for confirmation before deleting files.",
            "Do not delete user files without explicit user approval.",
            "Never remove files.",
            "删除文件前必须取得用户确认。",
            "删除前必须征得确认。",
            "刪除檔案前必須取得使用者確認。",
        ]
        cases += [block for block in guardrails.TEMPLATES.values()]
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(_deletion_guardrail_evidence(text))

    def test_command_specific_bans_are_not_claimed_as_general_approval_policies(self):
        for text in (
            "Never use `rm -rf`.", "**NEVER** use `rm`, `rmdir`, or `rm -rf` under any circumstances",
            "禁止执行 rm -rf。", "不得執行 rm -rf。",
        ):
            with self.subTest(text=text):
                self.assertEqual(_deletion_guardrail_evidence(text), [{"line": 1, "kind": "specific_command_ban"}])

    def test_examples_quotes_comments_and_weak_or_reversed_statements_are_not_evidence(self):
        for text in (
            "Run tests.", "rm -rf", "Consider asking before deleting files.",
            "Example: Never use rm.", "If needed, never use rm.",
            "Do not forget to delete files.", "Never skip deleting files.",
            "Do not delete files without user confirmation unless it is urgent.",
            "Before deleting files, do not ask for confirmation.",
            "Before deleting files, ask for confirmation?", "Never use rm except for build output.",
            "```text\nNever use rm.\n```", "```\nNever use rm.\n",
            "    Never use rm.", "\tNever use rm.", "> Never use rm.",
            '"Never use rm."', "`Never use rm.`", "## Never use rm.",
            "<!--\nNever use rm.\n-->", "<!-- Never use rm. -->", "Never use rm. <!-- example -->",
            "---\ndescription: |\n  Never use rm.\n---\nRun tests.",
            "---\nNever use rm.\n", "禁止忘记删除文件。",
        ):
            with self.subTest(text=text):
                self.assertEqual(_deletion_guardrail_evidence(text), [])

    def test_line_numbers_survive_bom_crlf_and_list_markup(self):
        text = "\ufeff# Safety\r\n\r\n- **Never** use `rm -rf`.\r\n"
        self.assertEqual(_deletion_guardrail_evidence(text), [{"line": 3, "kind": "specific_command_ban"}])

    def test_explicit_example_sections_are_not_active_policy(self):
        for heading in ("## Examples", "## **Examples:**", "## Sample", "## 示例：", "## 範例", "Examples\n--------"):
            with self.subTest(heading=heading):
                text = heading + "\n\nNever use rm.\n### Nested\nNever remove files.\n"
                self.assertEqual(_deletion_guardrail_evidence(text), [])

    def test_example_scope_ends_at_an_equal_or_shallower_heading(self):
        for heading in ("## Safety", "# Safety", "Safety\n------"):
            with self.subTest(heading=heading):
                text = "## Examples\n### Sample\nNever use rm.\n" + heading + "\n- Never remove files.\n"
                self.assertEqual(_deletion_guardrail_evidence(text), [
                    {"line": len(text.splitlines()), "kind": "file_deletion_constraint"},
                ])

    def test_html_layout_is_not_interpreted_as_active_policy(self):
        for text in (
            "<pre>\nNever use rm.\n</pre>\n",
            "<details>\n<summary>Example</summary>\nNever use rm.\n</details>\n",
            "<div\nclass='example'>\nNever use rm.\n</div>\n",
            "Never remove files.\n<br>\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(_deletion_guardrail_evidence(text), [])


class GuardrailWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "AGENTS.md"
        self.source.write_bytes(b"Run tests.\n")

    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def link(self, destination, target):
        try:
            os.symlink(target, destination)
        except OSError:
            self.skipTest("host does not permit symbolic links")

    def test_default_preview_is_unscored_read_only_and_has_no_raw_input_text(self):
        private = b"private source text with no guardrail\n"
        self.source.write_bytes(private)
        score = analyze(self.root).score
        result = guardrails.review_guardrails(self.root)
        self.assertEqual(result.status, "review_needed")
        self.assertRegex(result.confirmation_token, r"^[0-9a-f]{64}$")
        self.assertNotIn(private.decode().strip(), json.dumps(result.to_dict()))
        self.assertNotIn(private.decode().strip(), repr(result))
        self.assertEqual(self.source.read_bytes(), private)
        self.assertEqual(analyze(self.root).score, score)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_cli_preview_and_confirmed_append_are_separate(self):
        original = self.source.read_bytes()
        code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--json"])
        self.assertEqual((code, stderr), (0, ""))
        preview = json.loads(stdout)
        self.assertTrue(preview["advisory_only"])
        self.assertFalse(preview["score_affected"])
        self.assertEqual(preview["scope"], "selected_file_only")
        self.assertEqual(self.source.read_bytes(), original)
        code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--apply", preview["confirmation_token"], "--json"])
        self.assertEqual((code, stderr), (0, ""))
        self.assertTrue(json.loads(stdout)["applied"])
        self.assertTrue(self.source.read_bytes().startswith(original))
        self.assertIn(preview["proposed_append"].encode(), self.source.read_bytes())

    def test_apply_is_idempotent_and_uses_canonical_recognition_in_all_template_languages(self):
        for language in guardrails.TEMPLATES:
            with self.subTest(language=language):
                original = b"Run tests.\n"
                self.source.write_bytes(original)
                preview = guardrails.review_guardrails(self.root, template_language=language)
                applied = guardrails.review_guardrails(self.root, template_language=language, apply=preview.confirmation_token)
                self.assertTrue(applied.applied)
                once = self.source.read_bytes()
                repeat = guardrails.review_guardrails(self.root, template_language=language, apply=preview.confirmation_token)
                self.assertEqual(repeat.status, "recognized")
                self.assertFalse(repeat.applied)
                self.assertEqual(self.source.read_bytes(), once)

    def test_bom_crlf_and_no_terminal_newline_preserve_original_bytes(self):
        for original in (b"Run tests.", b"Run tests.\r\n", b"\xef\xbb\xbfRun tests.\r\n", b""):
            with self.subTest(original=original):
                self.source.write_bytes(original)
                preview = guardrails.review_guardrails(self.root)
                guardrails.review_guardrails(self.root, apply=preview.confirmation_token)
                changed = self.source.read_bytes()
                self.assertTrue(changed.startswith(original))
                if b"\r\n" in original:
                    self.assertNotIn(b"\n", changed[len(original):].replace(b"\r\n", b""))
                self.assertEqual(guardrails.review_guardrails(self.root).status, "recognized")

    def test_stale_content_or_language_token_cannot_apply(self):
        preview = guardrails.review_guardrails(self.root)
        original = self.source.read_bytes()
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(self.root, template_language="simplified", apply=preview.confirmation_token)
        self.source.write_bytes(original + b"Keep changes small.\n")
        current = self.source.read_bytes()
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(self.root, apply=preview.confirmation_token)
        self.assertEqual(self.source.read_bytes(), current)

    def test_mixed_newlines_preserve_the_prefix_and_use_lf_for_additions(self):
        for original in (b"First\rSecond\r\n", b"First\nSecond\r\n"):
            with self.subTest(original=original):
                self.source.write_bytes(original)
                preview = guardrails.review_guardrails(self.root)
                guardrails.review_guardrails(self.root, apply=preview.confirmation_token)
                current = self.source.read_bytes()
                self.assertTrue(current.startswith(original))
                self.assertNotIn(b"\r", current[len(original):])

    def test_replacement_with_identical_content_requires_a_fresh_preview(self):
        preview = guardrails.review_guardrails(self.root)
        original = self.source.read_bytes()
        self.source.rename(self.root / "old.txt")
        self.source.write_bytes(original)
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(self.root, apply=preview.confirmation_token)
        self.assertEqual(self.source.read_bytes(), original)

    def test_closed_mdc_frontmatter_and_target_path_are_preserved(self):
        target = self.root / ".cursor" / "rules" / "project.mdc"
        target.parent.mkdir(parents=True)
        original = b"---\ndescription: Project workflow\nalwaysApply: true\n---\nRun tests.\n"
        target.write_bytes(original)
        preview = guardrails.review_guardrails(self.root, file=".cursor/rules/project.mdc")
        guardrails.review_guardrails(self.root, file=preview.file, apply=preview.confirmation_token)
        self.assertTrue(target.read_bytes().startswith(original))
        self.assertEqual(self.source.read_bytes(), b"Run tests.\n")

    def test_adding_a_constraint_does_not_hide_existing_dangerous_instructions(self):
        self.source.write_text("Run rm -rf cache.\n", encoding="utf-8")
        before = analyze(self.root)
        preview = guardrails.review_guardrails(self.root)
        guardrails.review_guardrails(self.root, apply=preview.confirmation_token)
        after = analyze(self.root)
        self.assertIn("rm-rf", [finding.code for finding in after.findings])
        self.assertEqual(before.score, after.score)

    def test_confirmation_is_bound_to_directory_and_filename(self):
        preview = guardrails.review_guardrails(self.root)
        (self.root / "CLAUDE.md").write_bytes(self.source.read_bytes())
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(self.root, file="CLAUDE.md", apply=preview.confirmation_token)
        other = self.root / "other"
        other.mkdir()
        (other / "AGENTS.md").write_bytes(self.source.read_bytes())
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(other, apply=preview.confirmation_token)

    def test_no_parent_or_cross_file_scope_is_silently_inherited(self):
        self.source.write_text("Never use rm.\n", encoding="utf-8")
        nested = self.root / "package"
        nested.mkdir()
        (nested / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("Run tests.\n", encoding="utf-8")
        for file in ("package/AGENTS.md", "CLAUDE.md"):
            with self.subTest(file=file):
                self.assertEqual(guardrails.review_guardrails(self.root, file=file).status, "review_needed")

    def test_path_escape_ignored_unsupported_and_missing_files_are_rejected(self):
        for file in ("../AGENTS.md", "/AGENTS.md", "C:/AGENTS.md", "C:AGENTS.md", "", "README.md", "missing/AGENTS.md"):
            with self.subTest(file=file), self.assertRaises(guardrails.GuardrailError):
                guardrails.review_guardrails(self.root, file=file)
        (self.root / ".agentconfigscoreignore").write_text("AGENTS.md\n", encoding="utf-8")
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(self.root)

    def test_internal_file_alias_is_preview_only_and_external_alias_is_not_read(self):
        actual = self.root / "shared.txt"
        actual.write_bytes(self.source.read_bytes())
        self.source.unlink()
        self.link(self.source, actual)
        report = guardrails.review_guardrails(self.root)
        self.assertIn("file_alias", report.manual_review_reasons)
        self.assertIsNone(report.confirmation_token)
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(self.root, apply="a" * 64)
        self.source.unlink()
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "private.txt"
            outside.write_text("outside private sentinel", encoding="utf-8")
            self.link(self.source, outside)
            with patch.object(guardrails, "_read_source", side_effect=AssertionError("must not open")):
                with self.assertRaises(OSError):
                    guardrails.review_guardrails(self.root)

    def test_hard_link_is_not_automatically_modified(self):
        try:
            os.link(self.source, self.root / "shared.txt")
        except OSError:
            self.skipTest("hard links unavailable")
        report = guardrails.review_guardrails(self.root)
        self.assertIn("shared_or_unknown_link_count", report.manual_review_reasons)
        self.assertIsNone(report.confirmation_token)

    def test_ambiguous_markup_disables_automatic_append(self):
        for text in ("```\nRun tests.\n", "<!-- pending\n", "<pre>Run tests.</pre>", "---\ndescription: pending\n"):
            with self.subTest(text=text):
                self.source.write_text(text, encoding="utf-8")
                report = guardrails.review_guardrails(self.root)
                self.assertEqual(report.status, "review_needed")
                self.assertTrue(report.manual_review_reasons)
                self.assertIsNone(report.confirmation_token)
                with self.assertRaises(guardrails.GuardrailError):
                    guardrails.review_guardrails(self.root, apply="a" * 64)

    def test_html_example_is_manual_review_not_a_recognized_guardrail(self):
        original = b"<pre>\nNever use rm.\n</pre>\n"
        self.source.write_bytes(original)
        report = guardrails.review_guardrails(self.root)
        self.assertEqual(report.status, "review_needed")
        self.assertEqual(report.evidence, ())
        self.assertIn("html_or_comment_markup", report.manual_review_reasons)
        self.assertIsNone(report.confirmation_token)
        self.assertEqual(self.source.read_bytes(), original)

    def test_appending_inside_an_unfinished_example_section_is_manual_only(self):
        for heading in ("# Examples", "## 示例", "Examples\n=======", "## Examples\n### Nested"):
            with self.subTest(heading=heading):
                original = (heading + "\n\nNever use rm.\n").encode("utf-8")
                self.source.write_bytes(original)
                report = guardrails.review_guardrails(self.root)
                self.assertEqual(report.status, "review_needed")
                self.assertEqual(report.evidence, ())
                self.assertIn("example_section_at_end", report.manual_review_reasons)
                self.assertIsNone(report.confirmation_token)
                with self.assertRaises(guardrails.GuardrailError):
                    guardrails.review_guardrails(self.root, apply="a" * 64)
                self.assertEqual(self.source.read_bytes(), original)

    def test_closed_example_sections_allow_a_recognizable_idempotent_append(self):
        for heading in ("# Workflow", "Workflow\n========"):
            with self.subTest(heading=heading):
                self.source.write_text("# Examples\nNever use rm.\n" + heading + "\nRun tests.\n", encoding="utf-8")
                report = guardrails.review_guardrails(self.root)
                self.assertEqual(report.evidence, ())
                self.assertNotIn("example_section_at_end", report.manual_review_reasons)
                self.assertIsNotNone(report.confirmation_token)
                guardrails.review_guardrails(self.root, apply=report.confirmation_token)
                once = self.source.read_bytes()
                repeated = guardrails.review_guardrails(self.root, apply=report.confirmation_token)
                self.assertEqual(repeated.status, "recognized")
                self.assertEqual(self.source.read_bytes(), once)

    def test_explicit_approval_bypass_directives_require_manual_resolution(self):
        for text in (
            "Before deleting files, do not ask for confirmation.",
            "Never ask for user confirmation before removing user files.",
            "Delete files without asking for confirmation.",
            "Always remove existing files without explicit user approval.",
            "删除文件前不要征求用户确认。",
            "刪除檔案前無需取得使用者授權。",
        ):
            with self.subTest(text=text):
                self.source.write_text(text + "\n", encoding="utf-8")
                original = self.source.read_bytes()
                before = analyze(self.root).score
                report = guardrails.review_guardrails(self.root)
                self.assertEqual(report.status, "review_needed")
                self.assertEqual(report.review_signals, ({"line": 1, "kind": "approval_bypass_directive"},))
                self.assertIn("opposing_approval_directive", report.manual_review_reasons)
                self.assertIsNone(report.confirmation_token)
                with self.assertRaises(guardrails.GuardrailError):
                    guardrails.review_guardrails(self.root, apply="a" * 64)
                self.assertEqual(self.source.read_bytes(), original)
                self.assertEqual(analyze(self.root).score, before)

    def test_a_recognized_ban_does_not_hide_an_opposing_approval_directive(self):
        self.source.write_text("Never use rm.\nDelete files without user approval.\n", encoding="utf-8")
        original = self.source.read_bytes()
        code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--json"])
        self.assertEqual((code, stderr), (0, ""))
        report = json.loads(stdout)
        self.assertEqual(report["status"], "review_needed")
        self.assertEqual(report["evidence"], [{"line": 1, "kind": "specific_command_ban"}])
        self.assertEqual(report["review_signals"], [{"line": 2, "kind": "approval_bypass_directive"}])
        self.assertIsNone(report["confirmation_token"])
        self.assertEqual(report["proposed_append"], "")
        code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--apply", "0" * 64, "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(self.source.read_bytes(), original)

    def test_approval_bypass_examples_and_ambiguous_statements_do_not_block_append(self):
        directive = "Delete files without user approval."
        for text in (
            "```text\n" + directive + "\n```\n", "> " + directive, '"' + directive + '"',
            "    " + directive, "Example: " + directive, "## Examples\n" + directive + "\n## Workflow\nRun tests.",
            "Never delete files without user approval.",
            "Delete files without user approval?", "If necessary, delete files without user approval.",
            "Delete files without user approval unless they are tracked.",
            "Do not ignore user approval before deleting files.",
        ):
            with self.subTest(text=text):
                self.source.write_text(text + "\n", encoding="utf-8")
                report = guardrails.review_guardrails(self.root)
                self.assertEqual(report.review_signals, ())
                self.assertNotIn("opposing_approval_directive", report.manual_review_reasons)
                if not report.evidence:
                    self.assertIsNotNone(report.confirmation_token)

    def test_bypass_signals_exclude_comments_and_frontmatter(self):
        for text in (
            "<!--\nDelete files without user approval.\n-->\nRun tests.\n",
            "---\ndescription: |\n  Delete files without user approval.\n---\nRun tests.\n",
        ):
            with self.subTest(text=text):
                self.source.write_text(text, encoding="utf-8")
                self.assertEqual(guardrails.review_guardrails(self.root).review_signals, ())

    def test_text_cli_signals_use_locations_not_private_source(self):
        self.source.write_text("private source sentinel\nDelete files without user approval.\n", encoding="utf-8")
        code, stdout, stderr = self.invoke(["guardrails", str(self.root)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("approval_bypass_directive at line 2", stdout)
        self.assertIn("automatic append unavailable", stdout)
        self.assertNotIn("private source sentinel", stdout)
        self.assertNotIn("Delete files without user approval.", stdout)

    def test_new_bypass_directive_invalidates_an_earlier_append_confirmation(self):
        preview = guardrails.review_guardrails(self.root)
        self.source.write_bytes(self.source.read_bytes() + b"Delete files without user approval.\n")
        original = self.source.read_bytes()
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(self.root, apply=preview.confirmation_token)
        self.assertEqual(self.source.read_bytes(), original)

    def test_signal_locations_survive_bom_crlf_list_and_inline_formatting(self):
        original = b"\xef\xbb\xbf# Safety\r\n\r\n- **Delete** files without `user approval`.\r\n"
        self.source.write_bytes(original)
        report = guardrails.review_guardrails(self.root)
        self.assertEqual(report.review_signals, ({"line": 3, "kind": "approval_bypass_directive"},))
        self.assertIsNone(report.confirmation_token)
        self.assertNotIn("Delete", json.dumps(report.to_dict()))
        self.assertEqual(self.source.read_bytes(), original)

    def test_confirmed_append_refuses_replaced_target_between_review_and_open(self):
        preview = guardrails.review_guardrails(self.root)
        original_apply = guardrails._apply_append

        def changed(root, path, expected, info, addition):
            path.write_bytes(expected + b"concurrent edit\n")
            return original_apply(root, path, expected, info, addition)

        with patch.object(guardrails, "_apply_append", side_effect=changed):
            with self.assertRaises(guardrails.GuardrailError):
                guardrails.review_guardrails(self.root, apply=preview.confirmation_token)
        self.assertNotIn(b"Deletion and overwrite safeguards", self.source.read_bytes())

    def test_external_alias_replacement_during_apply_cannot_write_outside(self):
        preview = guardrails.review_guardrails(self.root)
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "private.txt"
            outside.write_bytes(b"outside sentinel\n")
            original_apply = guardrails._apply_append

            def replaced(root, path, expected, info, addition):
                path.unlink()
                self.link(path, outside)
                return original_apply(root, path, expected, info, addition)

            with patch.object(guardrails, "_apply_append", side_effect=replaced):
                with self.assertRaises((guardrails.GuardrailError, OSError)):
                    guardrails.review_guardrails(self.root, apply=preview.confirmation_token)
            self.assertEqual(outside.read_bytes(), b"outside sentinel\n")

    def test_partial_write_reports_failure_without_truncating_original(self):
        preview = guardrails.review_guardrails(self.root)
        original = self.source.read_bytes()
        write = os.write

        def partial(descriptor, addition):
            return write(descriptor, addition[:10])

        with patch.object(guardrails.os, "write", side_effect=partial):
            code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--apply", preview.confirmation_token, "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("incomplete", stderr)
        self.assertTrue(self.source.read_bytes().startswith(original))
        self.assertEqual(len(self.source.read_bytes()), len(original) + 10)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixture requires POSIX")
    def test_source_replaced_by_fifo_before_read_is_rejected_without_blocking(self):
        read_source = guardrails._read_source

        def replaced(root, path, target):
            path.unlink()
            os.mkfifo(path)
            return read_source(root, path, target)

        with patch.object(guardrails, "_read_source", side_effect=replaced):
            with self.assertRaises((guardrails.GuardrailError, OSError)):
                guardrails.review_guardrails(self.root)

    def test_invalid_utf8_large_sources_and_write_failures_do_not_emit_success(self):
        for content in (b"\xff", b"x" * (guardrails.MAX_SOURCE_BYTES + 1)):
            self.source.write_bytes(content)
            code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--json"])
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("error:", stderr)
        self.source.write_bytes(b"Run tests.\n")
        preview = guardrails.review_guardrails(self.root)
        with patch.object(guardrails.os, "write", side_effect=PermissionError("private detail")):
            code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--apply", preview.confirmation_token, "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertNotIn("private detail", stderr)
        self.assertEqual(self.source.read_bytes(), b"Run tests.\n")

    def test_text_cli_warns_about_review_scope_and_never_prints_old_content(self):
        self.source.write_text("private source sentinel\n", encoding="utf-8")
        code, stdout, stderr = self.invoke(["guardrails", str(self.root)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("No files changed", stdout)
        self.assertIn("Selected file only", stdout)
        self.assertNotIn("private source sentinel", stdout)


if __name__ == "__main__":
    unittest.main()
