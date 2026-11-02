import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("regression_lab", ROOT / "scripts" / "run_regression_lab.py")
LAB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAB)


class RegressionLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = LAB.evaluate()
        cls.rows = {row["id"]: row["observations"] for row in cls.result["scenarios"]}

    def test_labeled_development_expectations_and_evidence_limits(self):
        self.assertTrue(self.result["all_expectations_matched"])
        self.assertEqual(len(self.rows), 5)
        self.assertEqual(self.result["evidence_tier"], "synthetic_development_demo")
        self.assertIsNone(self.result["independent_accuracy_estimate"])
        self.assertFalse(self.result["ai_comparison_run"])
        self.assertFalse(self.result["user_adoption_established"])
        for key in ("scenario_sha256", "runner_sha256"):
            self.assertRegex(self.result[key], r"^[a-f0-9]{64}$")

    def test_equal_scores_can_still_block_a_removal_or_reversal(self):
        for name in ("root_moved_into_subtree", "exact_directive_reversed"):
            with self.subTest(name=name):
                row = self.rows[name]
                self.assertEqual((row["baseline_gate"]["base_score"], row["baseline_gate"]["head_score"]), (100, 100))
                self.assertEqual(row["baseline_gate"]["exit_code"], 1)
                self.assertEqual(row["score_only"]["exit_code"], 0)
                self.assertEqual(row["baseline_gate"]["new_errors"], row["score_only"]["new_errors"])

    def test_candidate_override_is_explicit_not_default_behavior(self):
        row = self.rows["candidate_weakens_thresholds"]
        self.assertEqual(row["baseline_gate"]["exit_code"], 1)
        self.assertEqual(row["candidate_threshold_override"]["exit_code"], 0)
        self.assertIn("--max-drop", row["candidate_threshold_override"]["command"])
        self.assertNotIn("--max-drop", row["baseline_gate"]["command"])

    def test_positive_controls_pass_in_every_mode(self):
        for name in ("unchanged", "same_directory_exact_rename"):
            self.assertEqual([self.rows[name][mode]["exit_code"] for mode in LAB.MODES], [0, 0, 0])

    def test_no_temp_paths_or_fixture_text_are_exposed_in_results(self):
        serialized = json.dumps(self.result)
        self.assertNotIn("acs-regression-lab-", serialized)
        self.assertNotIn("https://example.invalid", serialized)
        self.assertIn("<BASE>", serialized)

    def test_unsafe_fixture_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("../escape", "/outside", "C:/outside", "..\\outside"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    LAB._write_tree(Path(directory), {name: "test"}, LAB.POLICY)

    def test_operational_failure_is_not_a_passing_observation(self):
        failure = subprocess.CompletedProcess([], 2, "", "private-operational-detail")
        with patch.object(LAB.subprocess, "run", return_value=failure):
            with self.assertRaises(RuntimeError):
                LAB._invoke(Path("base"), Path("head"), [], {})

    def test_subprocess_identity_mismatch_is_not_relabelled(self):
        response = json.dumps({"base": {"tool": {"version": "different"}}, "head": {"tool": {}}})
        with patch.object(LAB.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, response, "")):
            with self.assertRaisesRegex(RuntimeError, "identity"):
                LAB._invoke(Path("base"), Path("head"), [], {})

    def test_retained_observations_replay_without_relabelling_tool_identity(self):
        retained = json.loads((ROOT / "examples" / "regression-lab" / "observed.json").read_text(encoding="utf-8"))
        self.assertEqual(retained["scenario_sha256"], self.result["scenario_sha256"])
        self.assertEqual(retained["scenarios"], self.result["scenarios"])
        self.assertEqual(retained["evidence_tier"], "synthetic_development_demo")
        self.assertIsNone(retained["independent_accuracy_estimate"])
        self.assertRegex(retained["tool"]["source_fingerprint"]["sha256"], r"^[a-f0-9]{64}$")

    def test_existing_report_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_bytes(b"preserved evidence")
            with patch.object(LAB, "evaluate") as evaluate, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(LAB.main(["--output", str(path)]), 2)
            evaluate.assert_not_called()
            self.assertEqual(path.read_bytes(), b"preserved evidence")

    def test_report_roundtrip_and_mismatch_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            stdout = io.StringIO()
            with patch.object(LAB, "evaluate", return_value=self.result), contextlib.redirect_stdout(stdout):
                self.assertEqual(LAB.main(["--output", str(path), "--json"]), 0)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), self.result)
            self.assertEqual(json.loads(stdout.getvalue()), self.result)
        with patch.object(LAB, "evaluate", return_value={**self.result, "all_expectations_matched": False}), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(LAB.main([]), 1)

    def test_render_preserves_interpretation_boundaries(self):
        text = LAB.render(self.result)
        self.assertIn("not independent accuracy", text)
        self.assertIn("intentionally weakened caller", text)
        self.assertIn("Positive controls are not safety certificates", text)


if __name__ == "__main__":
    unittest.main()
