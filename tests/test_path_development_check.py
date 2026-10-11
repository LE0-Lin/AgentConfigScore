import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_path_development_check import development_policy
from run_review_comparison import _digest, _tool_fingerprint, load_corpus


class DevelopmentReuseTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / "benchmarks" / "prospective-review-v1"
        self.frozen = json.loads((self.base / "tool-probe" / "replay-protocol.json").read_text(encoding="utf-8"))
        self.reuse = json.loads((self.base / "development-reuse.json").read_text(encoding="utf-8"))

    def test_current_code_policy_never_modifies_frozen_protocol(self):
        original = _digest(self.frozen)
        policy = development_policy(self.frozen)
        self.assertEqual(_digest(self.frozen), original)
        self.assertEqual(original, self.reuse["frozen_protocol_sha256"])
        self.assertEqual(policy["tool_source_sha256"], _tool_fingerprint())
        for key, value in self.frozen.items():
            if key != "tool_source_sha256":
                self.assertEqual(policy[key], value)

    def test_reused_case_keeps_original_inputs_and_unresolved_reference(self):
        corpus = load_corpus(self.base / "context" / "corpus.json")
        report = json.loads((self.base / "tool-probe" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(_digest(corpus), self.reuse["frozen_context_corpus_sha256"])
        self.assertEqual(_digest(report), self.reuse["frozen_tool_report_sha256"])
        self.assertEqual(report["source_revision"], self.reuse["source_revision"])
        self.assertEqual(self.reuse["status"], "development_reuse_not_independent_holdout")
        self.assertEqual(self.reuse["annotations"], [])
        self.assertFalse(self.reuse["comparison_ready"])
        self.assertIsNone(self.reuse["correctness_metrics"])
        self.assertTrue(all(case["label"] == "unresolved" for case in corpus["cases"]))

    def test_development_runner_help_is_offline_and_explicit(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_path_development_check.py"), "--help"],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DEVELOPMENT", result.stdout)
        self.assertIn("--archive", result.stdout)
        self.assertIn("--output-dir", result.stdout)

    def test_existing_output_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "sentinel.txt"
            sentinel.write_text("preserve\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "run_path_development_check.py"),
                 "--archive", str(Path(directory) / "absent.tar.gz"), "--output-dir", directory],
                capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")
            self.assertFalse((Path(directory) / "report.json").exists())

    def test_retained_development_check_does_not_become_accuracy_evidence(self):
        report = json.loads((self.base / "tool-probe" / "development" / "report.json").read_text(encoding="utf-8"))
        frozen_report = json.loads((self.base / "tool-probe" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "development_check_not_independent_evaluation")
        self.assertTrue(report["used_for_rule_development"])
        self.assertEqual(report["development_reuse_sha256"], _digest(self.reuse))
        self.assertEqual(report["frozen_protocol_sha256"], _digest(self.frozen))
        for key in ("source_revision", "context_corpus_sha256", "packet_sha256", "snapshot", "input_verification"):
            self.assertEqual(report[key], frozen_report[key])
        self.assertEqual(report["archive"]["archive_sha256"], frozen_report["archive"]["archive_sha256"])
        self.assertFalse(report["comparison_ready"])
        self.assertIsNone(report["correctness_metrics"])
        self.assertEqual(report["human_reference_status"], "unreviewed")
        self.assertEqual(report["hybrid_status"], "not_run")
        self.assertNotEqual(report["tool_source_sha256"], frozen_report["tool_source_sha256"])
        for scope in ("native_discovery", "root_instruction_scope"):
            self.assertEqual(report[scope]["files"], frozen_report[scope]["files"])
            self.assertEqual(report[scope]["suppressed_findings"], [])
            self.assertEqual([f["code"] for f in report[scope]["findings"]], ["context-large"])
            self.assertTrue(report[scope]["review_needed"])


if __name__ == "__main__":
    unittest.main()
