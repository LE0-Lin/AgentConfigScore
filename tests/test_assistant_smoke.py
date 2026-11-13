import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples/approval-gate/assistant_smoke.py"


class AssistantBridgeTests(unittest.TestCase):
    def test_retained_projection_matches_sources_and_contains_no_raw_grant(self):
        report = json.loads((SCRIPT.parent / "assistant-recorded/result.json").read_text(encoding="utf-8"))
        for key, source in (("bridge_sha256_lf", SCRIPT), ("gate_sha256_lf", SCRIPT.with_name("gate.py"))):
            self.assertEqual(report[key], hashlib.sha256(source.read_text(encoding="utf-8").encode()).hexdigest())
        self.assertEqual(report["evidence_tier"], "caller_operated_smoke")
        self.assertFalse(report["model_identity_attested"])
        for row in report["transcript"]:
            if "approval" in row["request"]:
                self.assertEqual(row["request"]["approval"], "<operator-grant-redacted>")

    def test_scripted_protocol_redacts_grant_and_checks_actual_effects(self):
        # This test uses scripted requests, not a model. The retained manual
        # assistant smoke is a separate, explicitly limited development record.
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result"
            with subprocess.Popen([sys.executable, str(SCRIPT), "--output-dir", str(output)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8") as process:
                try:
                    ready = json.loads(process.stdout.readline())
                    self.assertEqual(ready["status"], "ready")

                    def send(path, token=None):
                        request = {"tool": "delete_file", "path": path}
                        if token:
                            request["approval"] = token
                        process.stdin.write(json.dumps(request) + "\n")
                        process.stdin.flush()
                        return json.loads(process.stdout.readline())

                    self.assertEqual(send("obsolete.txt")["result"]["reason"], "approval_required")
                    grant = json.loads(process.stdout.readline())
                    token = grant["approval"]
                    self.assertEqual(send("keep.txt", token)["result"]["reason"], "approval_target_mismatch")
                    self.assertTrue(send("obsolete.txt", token)["result"]["executed"])
                    self.assertEqual(json.loads(process.stdout.readline())["event"], "fixture_reset")
                    self.assertEqual(send("obsolete.txt", token)["result"]["reason"], "approval_already_used")
                    remaining, error = process.communicate(timeout=10)
                    self.assertEqual(process.returncode, 0, error)
                    self.assertEqual(json.loads(remaining)["status"], "completed")
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()
            raw = (output / "result.json").read_text(encoding="utf-8")
            self.assertNotIn(token, raw)
            report = json.loads(raw)
            self.assertFalse(report["caller_identity_attested_by_bridge"])
            self.assertFalse(report["agent_isolation_validated"])
            self.assertIsNone(report["independent_accuracy_estimate"])
            self.assertEqual(report["actual_temporary_file_deletions"], 1)
            self.assertTrue(all(r["filesystem_postcondition_verified"] and r["unrelated_file_preserved"]
                                for r in report["transcript"]))
            self.assertEqual(report["bridge_sha256_lf"], hashlib.sha256(
                SCRIPT.read_text(encoding="utf-8").encode("utf-8")).hexdigest())

    def test_incomplete_invalid_and_unexpected_inputs_cannot_complete(self):
        for data, code in (("", 1), ("not json\n", 2), ("x" * 4097 + "\n", 2),
                           ('{"tool":"shell","path":"obsolete.txt"}\n', 1)):
            with self.subTest(code=code, length=len(data)), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "result"
                result = subprocess.run([sys.executable, str(SCRIPT), "--output-dir", str(output)],
                                        input=data, capture_output=True, text=True, encoding="utf-8", timeout=10)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertFalse((output / "result.json").exists())

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "keep.txt"
            marker.write_bytes(b"previous evidence")
            result = subprocess.run([sys.executable, str(SCRIPT), "--output-dir", directory],
                                    input="", capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(marker.read_bytes(), b"previous evidence")


if __name__ == "__main__":
    unittest.main()
