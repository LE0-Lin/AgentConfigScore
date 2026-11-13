import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("approval_gate_example", ROOT / "examples/approval-gate/gate.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class ApprovalGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="acs-approval-test-")
        self.addCleanup(temp.cleanup)
        self.parent = Path(temp.name).resolve()
        self.root = self.parent / "workspace"
        self.root.mkdir()
        self.file = self.root / "obsolete.txt"
        self.file.write_bytes(b"reviewed content\n")
        self.outside = self.parent / "outside.txt"
        self.outside.write_bytes(b"preserve outside\n")
        self.clock = [100.0]
        self.operator, self.delete = GATE.create_session(self.root, clock=lambda: self.clock[0])

    def request(self, **changes):
        return {"tool": "delete_file", "path": "obsolete.txt", **changes}

    def test_missing_and_forged_authority_cannot_delete(self):
        for changes, reason in (({}, "approval_required"), ({"approval": "invented-token"}, "invalid_approval"),
                                ({"approved": True}, "invalid_request_schema"),
                                ({"approval": {"approved": True}}, "invalid_approval")):
            with self.subTest(changes=changes):
                result = self.delete(self.request(**changes))
                self.assertEqual(result["reason"], reason)
                self.assertFalse(result["executed"])
                self.assertEqual(self.file.read_bytes(), b"reviewed content\n")

    def test_registered_delete_and_single_use_approval(self):
        token = self.operator.approve("obsolete.txt")
        self.assertTrue(self.delete(self.request(approval=token))["executed"])
        self.assertFalse(self.file.exists())
        self.file.write_bytes(b"new file, new intent\n")
        result = self.delete(self.request(approval=token))
        self.assertEqual(result["reason"], "approval_already_used")
        self.assertEqual(self.file.read_bytes(), b"new file, new intent\n")
        self.assertEqual(self.outside.read_bytes(), b"preserve outside\n")

    def test_expiry_boundary_is_rejected(self):
        token = self.operator.approve("obsolete.txt", ttl_seconds=1)
        self.clock[0] = 101.0
        self.assertEqual(self.delete(self.request(approval=token))["reason"], "approval_expired")
        self.assertTrue(self.file.exists())

    def test_request_path_and_session_are_bound(self):
        (self.root / "other.txt").write_bytes(b"other\n")
        token = self.operator.approve("obsolete.txt")
        self.assertEqual(self.delete(self.request(path="other.txt", approval=token))["reason"], "approval_target_mismatch")
        _, other_session = GATE.create_session(self.root)
        self.assertEqual(other_session(self.request(approval=token))["reason"], "invalid_approval")
        self.assertTrue(self.file.exists())
        self.assertTrue((self.root / "other.txt").exists())

    def test_changed_content_requires_new_approval(self):
        token = self.operator.approve("obsolete.txt")
        self.file.write_bytes(b"changed content\n")
        self.assertEqual(self.delete(self.request(approval=token))["reason"], "approved_state_changed")
        self.assertEqual(self.file.read_bytes(), b"changed content\n")

    def test_replacement_with_identical_bytes_requires_new_approval(self):
        token = self.operator.approve("obsolete.txt")
        replacement = self.root / "replacement.txt"
        replacement.write_bytes(self.file.read_bytes())
        os.replace(replacement, self.file)
        self.assertEqual(self.delete(self.request(approval=token))["reason"], "approved_state_changed")
        self.assertTrue(self.file.exists())

    def test_replaced_parent_directory_requires_new_approval(self):
        (self.root / "nested").mkdir()
        (self.root / "nested/file.txt").write_bytes(b"a")
        token = self.operator.approve("nested/file.txt")
        # Explicit, verified sibling destinations inside this disposable fixture.
        (self.root / "nested").rename(self.root / "old-nested")
        (self.root / "nested").mkdir()
        (self.root / "nested/file.txt").write_bytes(b"a")
        result = self.delete(self.request(path="nested/file.txt", approval=token))
        self.assertEqual(result["reason"], "approved_state_changed")
        self.assertTrue((self.root / "nested/file.txt").exists())

    def test_paths_and_unregistered_tools_are_refused(self):
        token = self.operator.approve("obsolete.txt")
        for path in ("../outside.txt", str(self.outside), "C:/outside.txt", "nested\\file.txt",
                     "a/../obsolete.txt", "./obsolete.txt", "obsolete.txt:stream", "NUL.txt", "a//b", "obsolete.txt."):
            with self.subTest(path=path):
                self.assertFalse(self.delete(self.request(path=path, approval=token))["executed"])
        self.assertEqual(self.delete(self.request(tool="shell", approval=token))["reason"], "unregistered_tool")
        self.assertTrue(self.file.exists())
        self.assertEqual(self.outside.read_bytes(), b"preserve outside\n")

    def test_hard_link_and_directory_are_not_approvable(self):
        (self.root / "directory").mkdir()
        with self.assertRaises(GATE.Refused):
            self.operator.approve("directory")
        try:
            os.link(self.file, self.root / "alias.txt")
        except OSError:
            self.skipTest("hard links unavailable on this filesystem")
        with self.assertRaises(GATE.Refused):
            self.operator.approve("obsolete.txt")
        self.assertTrue(self.file.exists())

    def test_file_and_parent_symlink_cannot_reach_outside(self):
        try:
            (self.root / "linked.txt").symlink_to(self.outside)
            (self.root / "linked-dir").symlink_to(self.parent, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation not permitted")
        for path in ("linked.txt", "linked-dir/outside.txt"):
            with self.subTest(path=path), self.assertRaises(GATE.Refused):
                self.operator.approve(path)
        self.assertEqual(self.outside.read_bytes(), b"preserve outside\n")

    def test_root_replacement_is_refused(self):
        token = self.operator.approve("obsolete.txt")
        self.root.rename(self.parent / "old-workspace")
        self.root.mkdir()
        self.file.write_bytes(b"new workspace content")
        self.assertEqual(self.delete(self.request(approval=token))["reason"], "workspace_changed")
        self.assertEqual(self.file.read_bytes(), b"new workspace content")

    def test_io_failure_is_error_and_does_not_allow_reuse(self):
        token = self.operator.approve("obsolete.txt")
        with patch.object(Path, "unlink", side_effect=PermissionError("private host detail")):
            result = self.delete(self.request(approval=token))
        self.assertEqual(result, {"decision": "error", "reason": "filesystem_error", "executed": None})
        self.assertEqual(self.delete(self.request(approval=token))["reason"], "approval_already_used")
        self.assertTrue(self.file.exists())
        self.assertNotIn(token, str(result))

    def test_invalid_lifetimes_and_large_files_are_refused(self):
        for ttl in (True, 0, -1, float("inf"), float("nan"), 61, "30"):
            with self.subTest(ttl=ttl), self.assertRaises(GATE.Refused):
                self.operator.approve("obsolete.txt", ttl_seconds=ttl)
        self.file.write_bytes(b"x" * (GATE.MAX_FILE_BYTES + 1))
        with self.assertRaises(GATE.Refused):
            self.operator.approve("obsolete.txt")


if __name__ == "__main__":
    unittest.main()
