import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "adversarial_cases.json"
RUNNER = ROOT / "scripts" / "run_adversarial_benchmark.py"
COMMITTED_REPORT = ROOT / "benchmarks" / "adversarial-v1-report.md"


class AdversarialBenchmarkTests(unittest.TestCase):
    def test_corpus_has_a_substantial_contract_and_explicit_challenges(self):
        corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
        self.assertEqual(corpus["schema_version"], 1)
        contract_count = (
            len(corpus["scan_templates"]) * len(corpus["file_variants"])
            + len(corpus["scan_cases"])
            + len(corpus["regression_cases"])
        )
        self.assertGreaterEqual(contract_count, 70)
        self.assertGreaterEqual(len(corpus["file_variants"]), 6)
        self.assertGreaterEqual(len(corpus["challenge_cases"]), 8)
        for case in corpus["challenge_cases"]:
            self.assertIs(case["expected_detection"], True)
            self.assertTrue(case["note"].strip())

    def test_runner_produces_metrics_and_keeps_misses_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            markdown = Path(directory) / "report.md"
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--output",
                    str(output),
                    "--markdown",
                    str(markdown),
                ],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(output.read_text(encoding="utf-8"))
            summary = result["contract_summary"]
            self.assertTrue(result["all_contracts_matched"])
            self.assertEqual(summary["cases"], summary["exact_matches"])
            self.assertEqual(summary["false_positives"], 0)
            self.assertEqual(summary["false_negatives"], 0)
            self.assertGreater(summary["clean_cases_passed"], 0)
            self.assertFalse(result["challenge_summary"]["gating"])
            self.assertGreater(result["challenge_summary"]["missed"], 0)
            rendered = markdown.read_text(encoding="utf-8")
            self.assertIn("Deterministic contract cases", rendered)
            self.assertIn("Open challenge set", rendered)
            self.assertIn("do not control the benchmark exit code", rendered)
            self.assertEqual(rendered, COMMITTED_REPORT.read_text(encoding="utf-8"))

    def test_runner_help_is_available_offline(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--help"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--markdown", completed.stdout)


if __name__ == "__main__":
    unittest.main()
