import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("behavior_probe", ROOT / "scripts/prepare_cursor_behavior_probe.py")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class BehaviorPreparationTests(unittest.TestCase):
    def prediction(self, source=None):
        return SimpleNamespace(returncode=0, stdout=json.dumps({"tool": {"version": "0.26.1",
            "source_fingerprint": {"sha256": source or PROBE.FROZEN_SOURCE}}}))

    def test_answer_keys_stay_outside_workspace_and_user_prompts(self):
        with tempfile.TemporaryDirectory() as directory:
            root, evidence = Path(directory) / "workspace", Path(directory) / "evidence"
            with patch.object(PROBE.subprocess, "run", return_value=self.prediction()):
                manifest = PROBE.prepare(root, evidence, Path(sys.executable))
            self.assertTrue((evidence / "behavior-manifest.json").is_file())
            self.assertFalse((root / "behavior-manifest.json").exists())
            self.assertEqual(len(set(manifest["markers"].values())), 4)
            self.assertEqual(manifest["status"], "prepared_no_native_behavior_results")
            for name, marker in manifest["markers"].items():
                self.assertIn(marker, (root / ".cursor/rules" / name).read_text(encoding="utf-8"))
                for case in manifest["cases"]:
                    self.assertNotIn(marker, case["prompt"])
                self.assertNotIn(marker, (root / "src/api/service.py").read_text(encoding="utf-8"))

    def test_nested_evidence_and_existing_inputs_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            with self.assertRaises(ValueError):
                PROBE.prepare(root, root / "answers", Path(sys.executable))
            root.mkdir()
            (root / "user-file.txt").write_text("preserve", encoding="utf-8")
            with self.assertRaises(ValueError):
                PROBE.prepare(root, Path(directory) / "evidence", Path(sys.executable))
            self.assertEqual((root / "user-file.txt").read_text(), "preserve")

    def test_different_runtime_source_never_becomes_a_completed_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            root, evidence = Path(directory) / "workspace", Path(directory) / "evidence"
            with patch.object(PROBE.subprocess, "run", return_value=self.prediction("0" * 64)):
                with self.assertRaises(ValueError):
                    PROBE.prepare(root, evidence, Path(sys.executable))
            self.assertFalse((evidence / "behavior-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
