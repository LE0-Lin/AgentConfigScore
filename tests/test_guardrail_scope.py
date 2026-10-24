"""Explicit guardrail selection must not certify or require a healthy whole tree."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score import guardrails, scanner
from agent_config_score.entrypoint import main


class GuardrailSelectionScopeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.source = self.root / "AGENTS.md"
        self.source.write_bytes(b"Run tests.\n")

    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def link(self, path, target, directory=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(target, path, target_is_directory=directory)
        except OSError:
            self.skipTest("host does not permit symbolic links")

    def test_preview_and_apply_do_not_walk_unrelated_directories(self):
        blocked = self.root / "unrelated"
        blocked.mkdir()
        original = self.source.read_bytes()
        with patch.object(scanner.os, "walk", side_effect=AssertionError("whole tree enumerated")):
            preview = guardrails.review_guardrails(self.root)
            self.assertEqual(preview.status, "review_needed")
            self.assertEqual(self.source.read_bytes(), original)
            applied = guardrails.review_guardrails(self.root, apply=preview.confirmation_token)
        self.assertTrue(applied.applied)
        self.assertTrue(self.source.read_bytes().startswith(original))

    def test_unselected_broken_source_does_not_block_review_but_full_scan_still_fails(self):
        broken = self.root / "nested" / "CLAUDE.md"
        self.link(broken, "absent.md")
        with self.assertRaises(OSError):
            scanner.analyze(self.root)
        code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--json"])
        self.assertEqual((code, stderr), (0, ""))
        preview = json.loads(stdout)
        self.assertEqual(preview["scope"], "selected_file_only")
        self.assertEqual(preview["file"], "AGENTS.md")
        code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--json",
                                           "--apply", preview["confirmation_token"]])
        self.assertEqual((code, stderr), (0, ""))
        self.assertTrue(json.loads(stdout)["applied"])
        self.assertEqual(os.readlink(broken), "absent.md")
        code, stdout, stderr = self.invoke([str(self.root), "--json"])
        self.assertEqual((code, stdout), (2, ""))

    def test_unselected_external_source_is_not_opened_or_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "private.txt"
            outside.write_bytes(b"outside sentinel\n")
            self.link(self.root / "CLAUDE.md", outside)
            with patch.object(guardrails, "_read_source", wraps=guardrails._read_source) as read:
                review = guardrails.review_guardrails(self.root)
            self.assertEqual(review.status, "review_needed")
            self.assertEqual([call.args[1] for call in read.call_args_list], [self.source])
            self.assertEqual(outside.read_bytes(), b"outside sentinel\n")

    def test_exclusion_patterns_and_skipped_ancestors_still_reject_selected_targets(self):
        cases = (("node_modules/client/AGENTS.md", ""), ("dist/AGENTS.md", ""),
                 ("package/AGENTS.md", "package/**\n"), ("package/CLAUDE.md", "*/CLAUDE.md\n"))
        for file, patterns in cases:
            with self.subTest(file=file):
                selected = self.root / file
                selected.parent.mkdir(parents=True, exist_ok=True)
                selected.write_bytes(b"Run tests.\n")
                (self.root / ".agentconfigscoreignore").write_text(patterns, encoding="utf-8")
                with patch.object(guardrails, "_read_source", side_effect=AssertionError("target read")):
                    with self.assertRaises(guardrails.GuardrailError):
                        guardrails.review_guardrails(self.root, file=file)

    def test_new_exclusion_after_preview_prevents_append(self):
        preview = guardrails.review_guardrails(self.root)
        (self.root / ".agentconfigscoreignore").write_text("AGENTS.md\n", encoding="utf-8")
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(self.root, apply=preview.confirmation_token)
        self.assertEqual(self.source.read_bytes(), b"Run tests.\n")

    def test_selected_directory_alias_is_not_traversed(self):
        actual = self.root / "actual"
        actual.mkdir()
        (actual / "AGENTS.md").write_bytes(b"Run tests.\n")
        self.link(self.root / "alias", actual, directory=True)
        with patch.object(guardrails, "_read_source", side_effect=AssertionError("alias target read")):
            with self.assertRaises((guardrails.GuardrailError, OSError)):
                guardrails.review_guardrails(self.root, file="alias/AGENTS.md")

    def test_selected_broken_alias_still_fails_before_reading(self):
        with patch.object(guardrails, "_read_source", side_effect=AssertionError("unsafe target read")):
            self.link(self.root / "CLAUDE.md", "absent.md")
            code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--file", "CLAUDE.md", "--json"])
        self.assertEqual((code, stdout), (2, ""))
        self.assertIn("error:", stderr)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixture requires POSIX")
    def test_unselected_nonregular_source_does_not_block_but_selected_fifo_is_rejected(self):
        fifo = self.root / "CLAUDE.md"
        os.mkfifo(fifo)
        with self.assertRaises(OSError):
            scanner.analyze(self.root)
        self.assertIsNotNone(guardrails.review_guardrails(self.root).confirmation_token)
        with patch.object(guardrails, "_read_source", side_effect=AssertionError("FIFO opened")):
            code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--file", "CLAUDE.md", "--json"])
        self.assertEqual((code, stdout), (2, ""))

    def test_ambiguous_directory_casing_requires_manual_selection(self):
        selected = self.root / "package" / "AGENTS.md"
        selected.parent.mkdir()
        selected.write_bytes(b"Run tests.\n")
        alternate = self.root / "Package"
        if alternate.exists():
            self.skipTest("case-insensitive filesystem")
        alternate.mkdir()
        with patch.object(guardrails, "_read_source", side_effect=AssertionError("ambiguous target read")):
            with self.assertRaises(guardrails.GuardrailError):
                guardrails.review_guardrails(self.root, file="package/AGENTS.md")

    def test_selected_parent_errors_do_not_expose_private_exception_details(self):
        selected = self.root / "package" / "AGENTS.md"
        selected.parent.mkdir()
        selected.write_bytes(b"Run tests.\n")
        original_resolve = Path.resolve

        def replaced(path, *args, **kwargs):
            if path == selected.parent:
                raise RuntimeError("private parent-loop detail")
            return original_resolve(path, *args, **kwargs)

        with patch.object(Path, "resolve", new=replaced):
            code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--file", "package/AGENTS.md", "--json"])
        self.assertEqual((code, stdout), (2, ""))
        self.assertNotIn("private parent-loop detail", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(selected.read_bytes(), b"Run tests.\n")

    def test_common_selection_rules_match_normal_discovery(self):
        files = ("CLAUDE.md", "nested/AGENTS.override.md", "nested/GEMINI.md", "literal/AGENTS.md",
                 ".cursor/rules/review.mdc", ".claude/review.md", ".github/instructions/review.md",
                 "node_modules/AGENTS.md", "excluded/AGENTS.md", ".cursor/rules/build/review.md", "docs/review.md")
        for file in files:
            target = self.root / file
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"Run tests.\n")
        (self.root / ".agentconfigscoreignore").write_text("literal\nexcluded/**\n", encoding="utf-8")
        discovered = set(scanner.discover(self.root))
        for file in ("AGENTS.md", *files):
            with self.subTest(file=file):
                chosen = scanner._select_instruction_source(self.root, file)
                self.assertEqual(chosen is not None, self.root / file in discovered)

    def test_regular_directory_does_not_override_a_supported_case_variant_file(self):
        selected = self.root / "nested" / "agents.md"
        selected.parent.mkdir()
        selected.write_bytes(b"Run tests.\n")
        alternate = selected.parent / "AGENTS.md"
        if alternate.exists():
            self.skipTest("case-insensitive filesystem")
        alternate.mkdir()
        self.assertEqual(guardrails.review_guardrails(self.root, file="nested/agents.md").file, "nested/agents.md")

    def test_unsafe_ignore_file_is_still_relevant_to_selected_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "private.txt"
            outside.write_bytes(b"external ignore sentinel\n")
            self.link(self.root / ".agentconfigscoreignore", outside)
            with patch.object(Path, "read_text", side_effect=AssertionError("external ignore read")):
                code, stdout, stderr = self.invoke(["guardrails", str(self.root), "--json"])
        self.assertEqual((code, stdout), (2, ""))
        self.assertNotIn("external ignore sentinel", stderr)

    def test_supported_selection_keeps_canonical_filename_precedence(self):
        alternate = self.root / "agents.md"
        if alternate.exists():
            self.skipTest("case-insensitive filesystem")
        alternate.write_bytes(b"Run different tests.\n")
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(self.root, file="agents.md")
        self.assertEqual(guardrails.review_guardrails(self.root).file, "AGENTS.md")

    def test_modern_rule_directory_accepts_supported_suffix_but_not_arbitrary_files(self):
        for file in (".cursor/rules/review.mdc", ".claude/review.md", ".github/instructions/review.md"):
            with self.subTest(file=file):
                selected = self.root / file
                selected.parent.mkdir(parents=True, exist_ok=True)
                selected.write_bytes(b"Run tests.\n")
                with patch.object(scanner.os, "walk", side_effect=AssertionError("whole tree enumerated")):
                    self.assertEqual(guardrails.review_guardrails(self.root, file=file).file, file)
        unsupported = self.root / "docs" / "review.md"
        unsupported.parent.mkdir()
        unsupported.write_bytes(b"Run tests.\n")
        with self.assertRaises(guardrails.GuardrailError):
            guardrails.review_guardrails(self.root, file="docs/review.md")


if __name__ == "__main__":
    unittest.main()
