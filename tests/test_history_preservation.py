import contextlib
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score.entrypoint import main
from agent_config_score.history import HISTORY_FILE, append_snapshot, load_history, summarize_history


class HistoryPreservationTests(unittest.TestCase):
    def _write(self, root, content):
        path = root / HISTORY_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_missing_history_is_empty_without_creating_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(load_history(root), [])
            self.assertEqual(list(root.iterdir()), [])

    def test_malformed_history_is_not_empty_or_overwritten(self):
        for content in (b"not-json", b"[{", b"\xff", b"{}", b"null", b"[{}, 9]", b'[{}, "private-fixture"]'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = self._write(root, content)
                with self.assertRaisesRegex(ValueError, "history"):
                    load_history(root)
                with self.assertRaisesRegex(ValueError, "history"):
                    append_snapshot(root, {"score": 100})
                self.assertEqual(path.read_bytes(), content)
                self.assertEqual(list(path.parent.iterdir()), [path])

    def test_duplicate_members_including_escaped_names_are_rejected(self):
        for content in (
            b'[{"score":90,"score":100}]',
            br'[{"score":90,"sc\u006fre":100}]',
            b'[{"tool":{"private-key":"private-value","private-key":"replacement"}}]',
        ):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = self._write(root, content)
                with self.assertRaisesRegex(ValueError, "history"):
                    load_history(root)
                self.assertEqual(path.read_bytes(), content)

    def test_nonstandard_and_overflow_json_numbers_are_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity", "1e9999"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._write(root, ('[{"extension":' + value + '}]').encode())
                with self.assertRaisesRegex(ValueError, "history"):
                    load_history(root)

    def test_invalid_scores_are_rejected_instead_of_included_in_trend(self):
        for value in (True, False, -1, 101, "100", [], {}):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._write(root, json.dumps([{"score": value}]).encode())
                with self.assertRaisesRegex(ValueError, "history"):
                    load_history(root)

    def test_partial_legacy_entries_and_extensions_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            items = [
                {"commit": "old"}, {"score": None, "tool": None},
                {"score": 90.5, "extension": {"notes": "保留記錄", "status": True}},
                {"score": 100, "tool": {"version": "historic"}},
            ]
            self._write(root, json.dumps(items, ensure_ascii=False).encode("utf-8"))
            self.assertEqual(load_history(root), items)
            summary = summarize_history(items)
            self.assertEqual((summary["count"], summary["scored_count"], summary["delta"]), (4, 2, 9.5))
            append_snapshot(root, {"commit": "new"})
            self.assertEqual(load_history(root), items + [{"commit": "new"}])

    def test_direct_summary_rejects_invalid_scores(self):
        for score in (True, float("nan"), float("inf"), -1, 101, "90"):
            with self.subTest(score=score), self.assertRaisesRegex(ValueError, "history"):
                summarize_history([{"score": score}])

    def test_read_permission_error_is_not_hidden_and_append_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write(root, b'[{"score":90}]')
            original = path.read_bytes()
            with patch.object(Path, "read_text", side_effect=PermissionError("private-io-detail")):
                with self.assertRaisesRegex(ValueError, "history"):
                    load_history(root)
                with self.assertRaisesRegex(ValueError, "history"):
                    append_snapshot(root, {"score": 100})
            self.assertEqual(path.read_bytes(), original)

    def test_cli_error_has_no_success_output_or_private_content(self):
        for as_json in (False, True):
            with self.subTest(as_json=as_json), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                content = b'[{"private-key":"private-value","private-key":"replacement"}]'
                path = self._write(root, content)
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = main(["history", str(root), *(["--json"] if as_json else [])])
                self.assertEqual(code, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("history", stderr.getvalue())
                for private in ("private-key", "private-value", "Traceback"):
                    self.assertNotIn(private, stderr.getvalue())
                self.assertEqual(path.read_bytes(), content)

    def test_limit_only_changes_visibility_not_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write(root, b'[9,{"score":100}]')
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main(["history", str(root), "--json", "--limit", "1"])
            self.assertEqual(code, 2)
            self.assertEqual(stdout.getvalue(), "")
            with self.assertRaisesRegex(ValueError, "history"):
                append_snapshot(root, {"score": 100}, limit=1)
            self.assertEqual(path.read_bytes(), b'[9,{"score":100}]')

    def test_invalid_snapshot_does_not_create_history(self):
        for snapshot in (None, [], {"score": True}, {"score": math.inf}, {"extension": object()}, {"text": "\ud800"}):
            with self.subTest(snapshot=repr(snapshot)), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                with self.assertRaises(ValueError):
                    append_snapshot(root, snapshot)
                self.assertEqual(list(root.iterdir()), [])

    def test_invalid_snapshot_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write(root, b'[{"score":90}]\n')
            for snapshot in ({"score": 101}, {"extension": math.nan}, {"extension": object()}):
                with self.subTest(snapshot=snapshot), self.assertRaises(ValueError):
                    append_snapshot(root, snapshot)
                self.assertEqual(path.read_bytes(), b'[{"score":90}]\n')

    def test_replacement_failure_keeps_history_and_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write(root, b'[{"score":90}]\n')
            with patch("os.replace", side_effect=PermissionError("private-replace-detail")):
                with self.assertRaisesRegex(ValueError, "history") as raised:
                    append_snapshot(root, {"score": 100})
            self.assertNotIn("private-replace-detail", str(raised.exception))
            self.assertEqual(path.read_bytes(), b'[{"score":90}]\n')
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_sync_failure_keeps_history_and_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write(root, b'[{"score":90}]\n')
            with patch("os.fsync", side_effect=OSError("private-sync-detail")):
                with self.assertRaisesRegex(ValueError, "history"):
                    append_snapshot(root, {"score": 100})
            self.assertEqual(path.read_bytes(), b'[{"score":90}]\n')
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_partial_temporary_write_failure_does_not_truncate_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write(root, b'[{"score":90}]\n')
            factory = tempfile.NamedTemporaryFile

            def failing_temporary(*args, **kwargs):
                target = factory(*args, **kwargs)
                real_write = target.write

                def interrupted_write(payload):
                    real_write(payload[:8])
                    raise OSError("synthetic-write-interruption")

                target.write = interrupted_write
                return target

            with patch("agent_config_score.history.tempfile.NamedTemporaryFile", side_effect=failing_temporary):
                with self.assertRaisesRegex(ValueError, "history"):
                    append_snapshot(root, {"score": 100})
            self.assertEqual(path.read_bytes(), b'[{"score":90}]\n')
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_successful_append_uses_complete_same_directory_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write(root, b'[{"score":90}]\n')
            original_replace = os.replace
            replacements = []

            def replace(source, destination):
                source, destination = Path(source), Path(destination)
                self.assertEqual(source.parent, destination.parent)
                self.assertEqual(destination.read_bytes(), b'[{"score":90}]\n')
                self.assertEqual(json.loads(source.read_text(encoding="utf-8")), [{"score": 90}, {"score": 100}])
                replacements.append((source, destination))
                return original_replace(source, destination)

            with patch("os.replace", side_effect=replace):
                self.assertEqual(append_snapshot(root, {"score": 100}), path)
            self.assertEqual(len(replacements), 1)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_nonregular_history_is_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / HISTORY_FILE
            path.mkdir(parents=True)
            with patch.object(Path, "read_text", side_effect=AssertionError("nonfile read")):
                with self.assertRaisesRegex(ValueError, "history"):
                    load_history(root)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO required")
    def test_fifo_history_is_rejected_without_opening_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / HISTORY_FILE
            path.parent.mkdir(parents=True)
            os.mkfifo(path)
            with patch.object(Path, "read_text", side_effect=AssertionError("FIFO opened")):
                with self.assertRaisesRegex(ValueError, "history"):
                    load_history(root)
                with self.assertRaisesRegex(ValueError, "history"):
                    append_snapshot(root, {"score": 100})

    def test_disappearing_index_is_read_error_not_missing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self._write(root, b'[{"score":90}]')
            with patch.object(Path, "read_text", side_effect=FileNotFoundError("removed during read")):
                with self.assertRaisesRegex(ValueError, "history"):
                    load_history(root)
            self.assertEqual(path.read_bytes(), b'[{"score":90}]')

    def test_parent_file_is_rejected_instead_of_hidden_as_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / ".agentconfigscore"
            parent.write_bytes(b"not a directory")
            with self.assertRaisesRegex(ValueError, "history"):
                load_history(root)
            with self.assertRaisesRegex(ValueError, "history"):
                append_snapshot(root, {"score": 100})
            self.assertEqual(parent.read_bytes(), b"not a directory")

    def test_linked_history_is_not_followed_or_replaced(self):
        for target_exists in (False, True):
            with self.subTest(target_exists=target_exists), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "repo"
                root.mkdir()
                outside = Path(directory) / "external.json"
                if target_exists:
                    outside.write_bytes(b'[{"score":90}]')
                path = root / HISTORY_FILE
                path.parent.mkdir(parents=True)
                try:
                    path.symlink_to(outside)
                except OSError:
                    self.skipTest("Host does not permit symbolic links")
                with patch.object(Path, "read_text", side_effect=AssertionError("alias read")):
                    with self.assertRaisesRegex(ValueError, "history"):
                        load_history(root)
                    with self.assertRaisesRegex(ValueError, "history"):
                        append_snapshot(root, {"score": 100})
                self.assertTrue(path.is_symlink())
                self.assertEqual(outside.exists(), target_exists)
                if target_exists:
                    self.assertEqual(outside.read_bytes(), b'[{"score":90}]')

    def test_linked_history_parent_is_rejected_before_creating_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root, outside = Path(directory) / "repo", Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            try:
                (root / ".agentconfigscore").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("Host does not permit symbolic links")
            with self.assertRaisesRegex(ValueError, "history"):
                load_history(root)
            with self.assertRaisesRegex(ValueError, "history"):
                append_snapshot(root, {"score": 100})
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
