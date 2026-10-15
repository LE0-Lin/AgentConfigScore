import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score.entrypoint import main
from agent_config_score.scanner import _repository_path_index, analyze, discover


class InstructionFilesystemTests(unittest.TestCase):
    def link(self, destination, target, *, directory=False):
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(target, destination, target_is_directory=directory)
        except OSError:
            self.skipTest("host does not permit symbolic links")

    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_external_instruction_is_rejected_before_reading_its_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            root = workspace / "repo"
            root.mkdir()
            target = workspace / "outside.txt"
            target.write_text("external sentinel\n", encoding="utf-8")
            self.link(root / "AGENTS.md", target)
            reads = []
            original = Path.read_text

            def record(path, *args, **kwargs):
                reads.append(path)
                return original(path, *args, **kwargs)

            with patch.object(Path, "read_text", new=record):
                with self.assertRaises(OSError):
                    analyze(root)
            self.assertNotIn(target, reads)
            self.assertNotIn(root / "AGENTS.md", reads)

    def test_internal_instruction_alias_keeps_its_scope_and_report_location(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "shared.txt"
            target.write_text("[Guide](guide.md)\nRun `rm -rf cache`.\n", encoding="utf-8")
            source = root / "packages" / "client" / "AGENTS.md"
            self.link(source, target)
            (source.parent / "guide.md").write_text("Guide\n", encoding="utf-8")
            report = analyze(root)
            self.assertEqual(report.files, ["packages/client/AGENTS.md"])
            self.assertFalse(any(f.code == "dead-path" for f in report.findings))
            finding = next(f for f in report.findings if f.code == "rm-rf")
            self.assertEqual((finding.file, finding.line), ("packages/client/AGENTS.md", 2))

    def test_broken_and_cyclic_instruction_links_are_not_clean_results(self):
        for kind in ("broken", "cycle", "external_chain"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory).resolve()
                root = workspace / "repo"
                root.mkdir()
                (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
                source = root / "CLAUDE.md"
                target = root / "chain.txt"
                self.link(source, target)
                if kind == "cycle":
                    self.link(target, source)
                elif kind == "external_chain":
                    outside = workspace / "outside.txt"
                    outside.write_text("external sentinel\n", encoding="utf-8")
                    self.link(target, outside)
                invocations = ([str(root), "--json"], ["compare", str(root), str(root), "--json"],
                               ["feedback", str(root), "--output", str(root / "feedback.md")])
                for args in invocations:
                    code, stdout, stderr = self.invoke(args)
                    self.assertEqual(code, 2)
                    self.assertEqual(stdout, "")
                    self.assertIn("error:", stderr)
                    self.assertNotIn("Traceback", stderr)
                    self.assertNotIn("external sentinel", stderr)
                    self.assertNotIn(str(workspace / "outside.txt"), stderr)
                self.assertFalse((root / "feedback.md").exists())

    def test_external_ignore_file_is_not_read(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            root = workspace / "repo"
            root.mkdir()
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            target = workspace / "outside.txt"
            target.write_text("external sentinel\n", encoding="utf-8")
            source = root / ".agentconfigscoreignore"
            self.link(source, target)
            with patch.object(Path, "read_text", side_effect=AssertionError("contents read")):
                with self.assertRaises(OSError):
                    discover(root)

    def test_internal_directory_aliases_are_not_traversed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            actual = root / "real"
            actual.mkdir()
            (actual / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            self.link(root / "alias", actual, directory=True)
            self.link(actual / "cycle", root, directory=True)
            self.assertEqual(discover(root), [actual / "AGENTS.md"])

    def test_non_instruction_link_cycle_does_not_crash_path_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            source = root / "loop.txt"
            self.link(source, source)
            index = _repository_path_index(root)
            self.assertNotIn("loop.txt", index)
            self.assertEqual(analyze(root).score, 100)

    def test_instruction_read_failure_is_operational_not_a_partial_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "AGENTS.md"
            source.write_text("Run tests.\n", encoding="utf-8")
            original = Path.read_text

            def unreadable(path, *args, **kwargs):
                if path == source:
                    raise PermissionError(13, "sensitive-error-detail")
                return original(path, *args, **kwargs)

            with patch.object(Path, "read_text", new=unreadable):
                code, stdout, stderr = self.invoke([str(root), "--json"])
                doctor_code, doctor_stdout, doctor_stderr = self.invoke(["doctor", str(root), "--json"])
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("Unable to read scanner source", stderr)
            self.assertNotIn("sensitive-error-detail", stderr)
            self.assertEqual((doctor_code, doctor_stderr), (1, ""))
            self.assertFalse(json.loads(doctor_stdout)["ok"])
            self.assertNotIn("sensitive-error-detail", doctor_stdout)

    def test_legacy_read_error_suppression_cannot_override_source_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source = root / "AGENTS.md"
            source.write_text("Run tests.\n", encoding="utf-8")
            config = {"version": 1, "suppressions": [{"rule": "read-error", "paths": ["**"],
                      "reason": "Historical report compatibility check", "expires": "2099-01-01"}]}
            (root / ".agentconfigscore.json").write_text(json.dumps(config), encoding="utf-8")
            original = Path.read_text

            def unreadable(path, *args, **kwargs):
                if path == source:
                    raise PermissionError(13, "sensitive-error-detail")
                return original(path, *args, **kwargs)

            with patch.object(Path, "read_text", new=unreadable):
                code, stdout, stderr = self.invoke([str(root), "--json"])
            self.assertEqual((code, stdout), (2, ""))
            self.assertIn("Unable to read scanner source", stderr)
            self.assertNotIn("sensitive-error-detail", stderr)

    def test_directory_alias_named_as_instruction_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "shared"
            target.mkdir()
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            self.link(root / "CLAUDE.md", target, directory=True)
            with self.assertRaises(OSError):
                discover(root)

    def test_unused_case_variant_does_not_override_selected_canonical_file(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            root = workspace / "repo"
            root.mkdir()
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            if (root / "agents.md").exists():
                self.skipTest("case-insensitive filesystem")
            outside = workspace / "outside.txt"
            outside.write_text("Run `rm -rf cache`.\n", encoding="utf-8")
            self.link(root / "agents.md", outside)
            report = analyze(root)
            self.assertEqual(report.files, ["AGENTS.md"])
            self.assertEqual(report.findings, [])

    def test_doctor_exposes_invalid_instruction_links_as_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            root = workspace / "repo"
            root.mkdir()
            target = workspace / "outside.txt"
            target.write_text("external sentinel\n", encoding="utf-8")
            self.link(root / "AGENTS.md", target)
            code, stdout, stderr = self.invoke(["doctor", str(root), "--json"])
            self.assertEqual((code, stderr), (1, ""))
            report = json.loads(stdout)
            self.assertFalse(report["ok"])
            self.assertEqual(next(c for c in report["checks"] if c["name"] == "instructions")["status"], "error")
            self.assertNotIn("external sentinel", stdout)
            self.assertNotIn(str(target), stdout)

    def test_read_time_guard_rejects_alias_changed_after_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            root = workspace / "repo"
            root.mkdir()
            inside, outside = root / "shared.txt", workspace / "outside.txt"
            inside.write_text("Run tests.\n", encoding="utf-8")
            outside.write_text("external sentinel\n", encoding="utf-8")
            source = root / "AGENTS.md"
            self.link(source, inside)
            reads = []
            original = Path.read_text

            def swapped(scan_root):
                selected = discover(scan_root)
                source.unlink()  # Only this test-owned alias, not its target.
                self.link(source, outside)
                return selected

            def record(path, *args, **kwargs):
                reads.append(path)
                return original(path, *args, **kwargs)

            with patch("agent_config_score.scanner.discover", side_effect=swapped), \
                    patch.object(Path, "read_text", new=record):
                code, stdout, stderr = self.invoke([str(root), "--json"])
            self.assertEqual((code, stdout), (2, ""))
            self.assertNotIn(outside, reads)
            self.assertNotIn(source, reads)
            self.assertNotIn("external sentinel", stderr)

    def test_ignored_external_instruction_is_not_selected_or_read(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            root = workspace / "repo"
            root.mkdir()
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            (root / ".agentconfigscoreignore").write_text("CLAUDE.md\n", encoding="utf-8")
            outside = workspace / "outside.txt"
            outside.write_text("Run `rm -rf cache`.\n", encoding="utf-8")
            self.link(root / "CLAUDE.md", outside)
            report = analyze(root)
            self.assertEqual(report.files, ["AGENTS.md"])
            self.assertEqual(report.findings, [])

    def test_internal_ignore_alias_works_and_broken_ignore_alias_fails(self):
        for exists in (True, False):
            with self.subTest(exists=exists), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
                target = root / "shared-ignore.txt"
                if exists:
                    target.write_text("CLAUDE.md\n", encoding="utf-8")
                self.link(root / ".agentconfigscoreignore", target)
                if exists:
                    self.assertEqual(discover(root), [root / "AGENTS.md"])
                else:
                    with self.assertRaises(OSError):
                        discover(root)

    def test_directory_glob_prunes_but_literal_directory_match_keeps_meaning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            nested = root / "package"
            nested.mkdir()
            for parent in (root, nested):
                (parent / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            ignore = root / ".agentconfigscoreignore"
            ignore.write_text("package\n", encoding="utf-8")
            self.assertEqual(discover(root), [root / "AGENTS.md", nested / "AGENTS.md"])
            ignore.write_text("package/**\n", encoding="utf-8")
            original = os.scandir

            def protected(path):
                if Path(path) == nested:
                    raise AssertionError("ignored tree was traversed")
                return original(path)

            with patch("agent_config_score.scanner.os.scandir", side_effect=protected):
                self.assertEqual(discover(root), [root / "AGENTS.md"])

    def test_discovery_keeps_the_callers_root_alias_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            root = workspace / "actual"
            nested = root / "package"
            nested.mkdir(parents=True)
            (nested / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            alias = workspace / "alias"
            self.link(alias, root, directory=True)
            self.assertEqual(discover(alias), [alias / "package" / "AGENTS.md"])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixtures require POSIX")
    def test_instruction_fifo_is_rejected_without_opening_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            os.mkfifo(root / "AGENTS.md")
            with patch.object(Path, "read_text", side_effect=AssertionError("FIFO opened")):
                with self.assertRaises(OSError):
                    analyze(root)

    @unittest.skipUnless(os.name == "nt", "junction fixture requires Windows")
    def test_windows_external_directory_junction_is_not_traversed(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            root, outside = workspace / "repo", workspace / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            (outside / "AGENTS.md").write_text("Run `rm -rf cache`.\n", encoding="utf-8")
            alias = root / "linked"
            result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(alias), str(outside)],
                                    capture_output=True, timeout=10)
            if result.returncode != 0:
                self.skipTest("host does not permit junction creation")
            self.assertEqual(discover(root), [root / "AGENTS.md"])
            self.assertEqual(analyze(root).findings, [])


if __name__ == "__main__":
    unittest.main()
