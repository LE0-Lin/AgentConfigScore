import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_native_probe", ROOT / "scripts/prepare_cursor_native_probe.py")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class NativeCaptureTests(unittest.TestCase):
    def run_capture(self, payload, directory):
        script = Path(directory) / "capture.py"
        script.write_text(PROBE.HOOK, encoding="utf-8")
        result = subprocess.run([sys.executable, "-I", "-X", "utf8", str(script), "beforeSubmitPrompt"],
                                input=json.dumps(payload), capture_output=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"continue": True})
        path = Path(directory) / "native-observations.jsonl"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def test_observation_records_structure_without_prompt_email_or_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_capture({"prompt": "CAPTURE_CONTROL_V2 secret-sentinel",
                "user_email": "private-sentinel@example.org", "content": "private-file-sentinel",
                "attachments": [{"type": "rule", "file_path": str(Path(directory) / "always.mdc"),
                                  "content": "private-rule-sentinel"}]}, directory)
            self.assertEqual(result["input_attachment_count"], 1)
            self.assertEqual(result["reported_attachments"], [{"type": "rule", "path": "always.mdc"}])
            self.assertEqual(result["recognized_probe_marker"], "CAPTURE_CONTROL_V2")
            encoded = json.dumps(result)
            self.assertNotIn("sentinel", encoded)
            self.assertNotIn(directory, encoded)

    def test_empty_missing_and_malformed_attachment_fields_are_distinguished(self):
        for payload, present, count in (({}, False, None), ({"attachments": []}, True, 0),
                                        ({"attachments": None}, True, None), ({"attachments": {}}, True, None)):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                result = self.run_capture(payload, directory)
                self.assertEqual(result["attachments_field_present"], present)
                self.assertEqual(result["input_attachment_count"], count)

    def test_filtered_entries_are_counted_without_leaking_their_values(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_capture({"attachments": [
                {"type": "unknown-private-sentinel", "filePath": "private-sentinel"},
                {"type": "rule", "filePath": "private-sentinel"},
                {"type": "file", "file_path": str(Path(directory).parent / "outside-private-sentinel")},
            ]}, directory)
            self.assertEqual(result["input_attachment_count"], 3)
            self.assertEqual(result["unsupported_attachment_count"], 1)
            self.assertEqual(result["unusable_attachment_path_count"], 1)
            self.assertEqual(result["outside_workspace_attachments_omitted"], 1)
            self.assertEqual(result["reported_attachments"], [])
            self.assertNotIn("sentinel", json.dumps(result))

    def test_non_object_input_is_not_a_successful_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(self.run_capture(["private-sentinel"], directory))


if __name__ == "__main__":
    unittest.main()
