"""Initialization scope and write boundaries in disposable local fixtures."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score.entrypoint import main
from agent_config_score import initializer


class InitWorkflowScopeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name).resolve()
        self.root = self.workspace / "repo"
        self.root.mkdir()
        self.policy = self.root / ".agentconfigscore.json"
        self.workflow = self.root / ".github" / "workflows" / "agent-config-score.yml"

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["init", str(self.root), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def link(self, path, target, *, directory=False):
        try:
            os.symlink(target, path, target_is_directory=directory)
        except OSError:
            self.skipTest("host does not permit symbolic links")

    def test_workflow_only_preserves_custom_policy_bytes_and_does_not_read_them(self):
        original = b'\xef\xbb\xbf{"version":1,"policy":{"max_drop":3,"fail_on_new_errors":false}}\r\n'
        self.policy.write_bytes(original)
        read_text = Path.read_text

        def guarded(path, *args, **kwargs):
            if path == self.policy:
                raise AssertionError("unselected policy must not be read")
            return read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", new=guarded):
            changes = initializer.initialize_repository(self.root, include_config=False, pr_comment=True)
        self.assertEqual([item.path.as_posix() for item in changes], [".github/workflows/agent-config-score.yml"])
        self.assertEqual(self.policy.read_bytes(), original)
        self.assertEqual(self.workflow.read_text(encoding="utf-8"), initializer.PR_COMMENT_WORKFLOW_CONTENT)

    def test_workflow_only_never_creates_a_missing_policy(self):
        code, stdout, stderr = self.invoke("--workflow-only")
        self.assertEqual((code, stderr), (0, ""))
        self.assertFalse(self.policy.exists())
        self.assertTrue(self.workflow.is_file())
        self.assertIn("Policy file is out of scope", stdout)
        self.assertIn("@v0", stdout)
        self.assertIn("may differ", stdout)
        self.assertIn("doctor", stdout)

    def test_force_workflow_upgrade_preserves_even_invalid_unselected_policy(self):
        initializer.initialize_repository(self.root)
        original = b"private-invalid-policy-\xff"
        self.policy.write_bytes(original)
        code, stdout, stderr = self.invoke("--workflow-only", "--pr-comment", "--force")
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(self.policy.read_bytes(), original)
        self.assertIn("pull-requests: write", stdout)
        self.assertNotIn("private-invalid-policy", stdout + stderr)
        self.assertIn("createComment", self.workflow.read_text(encoding="utf-8"))

    def test_workflow_upgrade_still_requires_explicit_overwrite_and_is_idempotent(self):
        initializer.initialize_repository(self.root)
        original = self.workflow.read_bytes()
        code, stdout, stderr = self.invoke("--workflow-only", "--pr-comment")
        self.assertEqual((code, stdout), (2, ""))
        self.assertIn("refusing to overwrite", stderr)
        self.assertEqual(self.workflow.read_bytes(), original)
        code, _, stderr = self.invoke("--workflow-only", "--pr-comment", "--force")
        self.assertEqual((code, stderr), (0, ""))
        once = self.workflow.read_bytes()
        code, stdout, stderr = self.invoke("--workflow-only", "--pr-comment")
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("unchanged", stdout)
        self.assertEqual(self.workflow.read_bytes(), once)

    def test_workflow_only_dry_run_and_contradictory_scope_write_nothing(self):
        code, stdout, stderr = self.invoke("--workflow-only", "--pr-comment", "--dry-run")
        self.assertEqual((code, stderr), (0, ""))
        self.assertIn("Dry run", stdout)
        self.assertEqual(list(self.root.iterdir()), [])
        code, stdout, stderr = self.invoke("--workflow-only", "--no-workflow")
        self.assertEqual((code, stdout), (2, ""))
        self.assertEqual(list(self.root.iterdir()), [])
        with self.assertRaises(initializer.InitError):
            initializer.initialize_repository(self.root, include_config=False, include_workflow=False)

    def test_unselected_policy_alias_is_not_read_or_changed(self):
        outside = self.workspace / "private.txt"
        outside.write_bytes(b"unselected private policy\xff")
        self.link(self.policy, outside)
        changes = initializer.initialize_repository(self.root, include_config=False, pr_comment=True)
        self.assertEqual(len(changes), 1)
        self.assertEqual(outside.read_bytes(), b"unselected private policy\xff")
        self.assertTrue(self.policy.is_symlink())

    def test_policy_only_does_not_inspect_an_unselected_workflow_directory_alias(self):
        outside = self.workspace / "outside"
        outside.mkdir()
        self.link(self.root / ".github", outside, directory=True)
        code, stdout, stderr = self.invoke("--no-workflow")
        self.assertEqual((code, stderr), (0, ""))
        self.assertTrue(self.policy.is_file())
        self.assertNotIn("Workflow uses", stdout)
        self.assertEqual(list(outside.iterdir()), [])

    def test_reported_action_ref_matches_both_generated_workflows(self):
        for template in (initializer.WORKFLOW_CONTENT, initializer.PR_COMMENT_WORKFLOW_CONTENT):
            self.assertIn("uses: " + initializer.WORKFLOW_ACTION_REF + "\n", template)

    @unittest.skipIf(os.name == "nt", "POSIX permission bits are required")
    def test_overwriting_a_regular_workflow_preserves_permissions(self):
        self.workflow.parent.mkdir(parents=True)
        self.workflow.write_bytes(b"custom workflow")
        self.workflow.chmod(0o640)
        initializer.initialize_repository(self.root, include_config=False, force=True)
        self.assertEqual(self.workflow.stat().st_mode & 0o777, 0o640)
        self.assertEqual(self.workflow.read_text(encoding="utf-8"), initializer.WORKFLOW_CONTENT)

    def test_selected_policy_alias_is_rejected_before_reading(self):
        outside = self.workspace / "private.txt"
        outside.write_bytes(b"private sentinel")
        self.link(self.policy, outside)
        with patch.object(Path, "read_text", side_effect=AssertionError("must not read aliased contents")):
            with self.assertRaises(initializer.InitError):
                initializer.initialize_repository(self.root, force=True)
        self.assertEqual(outside.read_bytes(), b"private sentinel")
        self.assertFalse(self.workflow.exists())

    def test_dangling_selected_alias_is_not_treated_as_a_new_file(self):
        outside = self.workspace / "missing.txt"
        self.link(self.policy, outside)
        code, stdout, stderr = self.invoke("--force")
        self.assertEqual((code, stdout), (2, ""))
        self.assertFalse(outside.exists())
        self.assertTrue(self.policy.is_symlink())

    def test_directory_alias_is_rejected_before_any_config_is_created(self):
        for internal in (False, True):
            with self.subTest(internal=internal), tempfile.TemporaryDirectory() as directory:
                workspace = Path(directory).resolve()
                root = workspace / "repo"
                root.mkdir()
                target = (root if internal else workspace) / "actual"
                target.mkdir()
                self.link(root / ".github", target, directory=True)
                with self.assertRaises(initializer.InitError):
                    initializer.initialize_repository(root, force=True)
                self.assertFalse((root / ".agentconfigscore.json").exists())
                self.assertEqual(list(target.iterdir()), [])

    def test_workflow_hard_link_cannot_overwrite_policy_or_shared_files(self):
        self.workflow.parent.mkdir(parents=True)
        self.policy.write_bytes(b"custom policy sentinel")
        try:
            os.link(self.policy, self.workflow)
        except OSError:
            self.skipTest("hard links unavailable")
        with self.assertRaises(initializer.InitError):
            initializer.initialize_repository(self.root, include_config=False, pr_comment=True, force=True)
        self.assertEqual(self.policy.read_bytes(), b"custom policy sentinel")
        self.assertEqual(self.workflow.read_bytes(), b"custom policy sentinel")

    def test_selected_nonfile_parent_and_target_are_rejected(self):
        (self.root / ".github").write_bytes(b"not a directory")
        with self.assertRaises(initializer.InitError):
            initializer.initialize_repository(self.root)
        self.assertFalse(self.policy.exists())
        (self.root / ".github").unlink()
        self.policy.mkdir()
        with self.assertRaises(initializer.InitError):
            initializer.initialize_repository(self.root, force=True)

    def test_exclusive_creation_does_not_overwrite_a_concurrently_created_target(self):
        real_open = initializer.os.open

        def appeared(path, flags, *args, **kwargs):
            if Path(path) == self.workflow and flags & os.O_EXCL:
                self.workflow.write_bytes(b"concurrent workflow")
            return real_open(path, flags, *args, **kwargs)

        with patch.object(initializer.os, "open", side_effect=appeared):
            with self.assertRaises(initializer.InitError):
                initializer.initialize_repository(self.root, include_config=False)
        self.assertEqual(self.workflow.read_bytes(), b"concurrent workflow")
        self.assertFalse(self.policy.exists())

    def test_hard_link_swap_before_open_is_rejected_without_writing(self):
        self.workflow.parent.mkdir(parents=True)
        self.workflow.write_bytes(b"existing workflow")
        outside = self.workspace / "private.txt"
        outside.write_bytes(b"outside sentinel")
        real_open = initializer.os.open

        def swapped(path, flags, *args, **kwargs):
            if Path(path) == self.workflow:
                self.workflow.unlink()
                os.link(outside, self.workflow)
            return real_open(path, flags, *args, **kwargs)

        with patch.object(initializer.os, "open", side_effect=swapped):
            with self.assertRaises(initializer.InitError):
                initializer.initialize_repository(self.root, include_config=False, force=True)
        self.assertEqual(outside.read_bytes(), b"outside sentinel")

    def test_fixed_operational_error_does_not_export_private_exception_details(self):
        lstat = Path.lstat

        def denied(path, *args, **kwargs):
            if path == self.root / ".github":
                raise PermissionError("private-error-sentinel")
            return lstat(path, *args, **kwargs)

        with patch.object(Path, "lstat", new=denied):
            code, stdout, stderr = self.invoke("--workflow-only", "--pr-comment")
        self.assertEqual((code, stdout), (2, ""))
        self.assertNotIn("private-error-sentinel", stderr)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixture requires POSIX")
    def test_fifo_target_is_rejected_without_reading_or_blocking(self):
        os.mkfifo(self.policy)
        with patch.object(Path, "read_text", side_effect=AssertionError("must not read FIFO")):
            with self.assertRaises(initializer.InitError):
                initializer.initialize_repository(self.root, force=True)

    @unittest.skipUnless(os.name == "nt", "junction fixture requires Windows")
    def test_windows_junction_parent_is_not_used_for_generated_files(self):
        outside = self.workspace / "outside"
        outside.mkdir()
        result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(self.root / ".github"), str(outside)],
                                capture_output=True, timeout=10)
        if result.returncode:
            self.skipTest("junction creation unavailable")
        with self.assertRaises(initializer.InitError):
            initializer.initialize_repository(self.root)
        self.assertFalse(self.policy.exists())
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
