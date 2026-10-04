import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_review_comparison.py"
CORPUS = ROOT / "benchmarks" / "review-calibration.json"
SPEC = importlib.util.spec_from_file_location("review_comparison", RUNNER)
COMPARISON = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPARISON)


class ReviewComparisonTests(unittest.TestCase):
    def setUp(self):
        self.corpus = COMPARISON.load_corpus(CORPUS)
        self.packet = COMPARISON.review_packet(self.corpus)

    def oracle(self, run_id="fixture-run"):
        # Deliberately perfect test oracle, NOT a measured AI/model response.
        data = COMPARISON.predictions_template(self.packet)
        data.update(reviewer="Unit-test oracle (not AI evidence)", run_id=run_id)
        labels = {COMPARISON._opaque_id(self.corpus, case): case["label"] for case in self.corpus["cases"]}
        for row in data["predictions"]:
            row["review_needed"] = None if labels[row["id"]] == "unresolved" else labels[row["id"]] == "review"
            row["reason"] = "Synthetic test oracle only."
        return data

    def load_modified(self, corpus):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            path.write_text(json.dumps(corpus), encoding="utf-8")
            return COMPARISON.load_corpus(path)

    def test_calibration_is_honest_about_known_inputs_and_labels(self):
        self.assertEqual(self.corpus["tier"], "calibration")
        self.assertTrue(self.corpus["used_for_rule_development"])
        self.assertEqual(self.corpus["label_status"], "provisional")
        self.assertEqual(len(self.corpus["cases"]), 12)
        self.assertTrue(all(case["source_kind"] == "synthetic" for case in self.corpus["cases"]))

    def test_export_is_allowlisted_and_does_not_leak_reference_metadata(self):
        corpus = copy.deepcopy(self.corpus)
        corpus["cases"][0].update(id="GOLD_CASE_NAME", rationale="GOLD_RATIONALE",
                                  category="GOLD_CATEGORY", source_ref="GOLD_PROVENANCE", private_note="PRIVATE_SENTINEL")
        packet = COMPARISON.review_packet(corpus)
        serialized = json.dumps(packet)
        for sentinel in ("GOLD_CASE_NAME", "GOLD_RATIONALE", "GOLD_CATEGORY", "GOLD_PROVENANCE", "PRIVATE_SENTINEL"):
            self.assertNotIn(sentinel, serialized)
        self.assertEqual(set(packet), {"schema_version", "prompt", "cases", "packet_sha256"})
        self.assertTrue(all(set(case) == {"id", "files"} for case in packet["cases"]))
        self.assertEqual(packet, COMPARISON.review_packet(corpus))

    def test_input_or_prompt_change_invalidates_import_but_label_change_does_not_leak(self):
        original = self.packet["packet_sha256"]
        changed = copy.deepcopy(self.corpus)
        changed["cases"][0]["label"] = "review"
        self.assertEqual(COMPARISON.review_packet(changed)["packet_sha256"], original)
        self.assertNotEqual(COMPARISON._digest(changed), COMPARISON._digest(self.corpus))
        changed["cases"][0]["files"]["AGENTS.md"] += "More context.\n"
        with self.assertRaises(ValueError):
            COMPARISON.validate_predictions(self.oracle(), COMPARISON.review_packet(changed))
        with patch.object(COMPARISON, "PROMPT", COMPARISON.PROMPT + "Changed protocol."):
            self.assertNotEqual(COMPARISON.review_packet(self.corpus)["packet_sha256"], original)

    def test_no_model_run_means_no_model_metrics(self):
        result = COMPARISON.evaluate(self.corpus, [])
        self.assertEqual(result["ai_status"], "not_run")
        self.assertEqual(result["comparisons"], [])
        self.assertEqual(result["tool"]["scored_cases"], 11)
        self.assertEqual(result["tool"]["excluded_unresolved_labels"], 1)
        self.assertEqual(result["tool"]["fn"], 1)
        self.assertEqual(result["tool"]["tp"], 6)
        self.assertEqual(result["tool_by_category"]["semantic"]["fn"], 1)
        self.assertEqual(result["tool_by_category"]["semantic"]["recall"], 0.6667)
        self.assertRegex(result["tool_source_sha256"], r"^[0-9a-f]{64}$")
        rendered = COMPARISON.markdown_report(result)
        self.assertIn("AI / hybrid | not run", rendered)
        self.assertEqual(rendered, (ROOT / "benchmarks" / "review-calibration-report.md").read_text(encoding="utf-8"))

    def test_complete_oracle_comparison_and_missing_cost_are_not_fabricated(self):
        result = COMPARISON.evaluate(self.corpus, [self.oracle()])
        run = result["comparisons"][0]
        self.assertEqual(run["ai"]["f1"], 1.0)
        self.assertEqual(run["hybrid_union"]["fn"], 0)
        self.assertTrue(all(value is None for value in run["usage"].values()))

    def test_missing_and_abstained_answers_never_count_as_clean(self):
        missing = self.oracle()
        missing["predictions"].pop(0)
        # Select a resolved label to abstain on, separate from the omitted row.
        for row in missing["predictions"]:
            if row["review_needed"] is not None:
                row["review_needed"] = None
                break
        result = COMPARISON.evaluate(self.corpus, [missing])
        run = result["comparisons"][0]
        self.assertEqual(run["missing_packet_cases"], 1)
        self.assertGreaterEqual(run["abstained_packet_cases"], 1)
        self.assertEqual(run["ai"]["status"], "incomplete")
        for key in ("precision", "recall", "f1", "accuracy"):
            self.assertIsNone(run["ai"][key])
        self.assertLess(run["ai"]["coverage"], 1)

    def test_hybrid_or_preserves_unknowns_and_can_add_false_positives(self):
        for left, right, expected in ((False, None, None), (True, None, True),
                                      (False, False, False), (False, True, True)):
            self.assertIs(COMPARISON._union(left, right), expected)
        ai = self.oracle()
        case = next(case for case in self.corpus["cases"] if case["id"] == "ordinary-verification")
        row = next(row for row in ai["predictions"] if row["id"] == COMPARISON._opaque_id(self.corpus, case))
        row["review_needed"] = True
        run = COMPARISON.evaluate(self.corpus, [ai])["comparisons"][0]
        self.assertEqual(run["ai"]["fp"], 1)
        self.assertEqual(run["hybrid_union"]["fp"], 1)
        self.assertEqual(run["ai"]["precision"], 0.875)
        self.assertEqual(run["ai"]["accuracy"], 0.9091)
        self.assertIn("ordinary-verification: false positive", COMPARISON.markdown_report(COMPARISON.evaluate(self.corpus, [ai])))

    def test_repeatability_compares_only_same_declared_reviewer(self):
        first, second = self.oracle("first"), self.oracle("second")
        row = next(row for row in second["predictions"] if row["review_needed"] is False)
        row["review_needed"] = True
        result = COMPARISON.evaluate(self.corpus, [first, second])
        self.assertEqual(result["stability"][0]["disagreement_cases"], 1)
        self.assertEqual(result["stability"][0]["comparable_cases"], 11)
        second["reviewer"] = "Different unit-test model identifier"
        self.assertEqual(COMPARISON.evaluate(self.corpus, [first, second])["stability"], [])

    def test_invalid_predictions_fail_before_any_scan(self):
        variants = []
        for key, value in (("packet_sha256", "wrong"), ("schema_version", True), ("reviewer", ""), ("run_id", "")):
            data = self.oracle()
            data[key] = value
            variants.append(data)
        for value in ("false", 0, 1, [], {}):
            data = self.oracle()
            data["predictions"][0]["review_needed"] = value
            variants.append(data)
        for field, value in (("reason", ""), ("id", "unknown")):
            data = self.oracle()
            data["predictions"][0][field] = value
            variants.append(data)
        data = self.oracle()
        data["predictions"].append(data["predictions"][0])
        variants.append(data)
        for data in variants:
            with self.subTest(data=data), patch.object(COMPARISON, "analyze", side_effect=AssertionError("must not scan")):
                with self.assertRaises(ValueError):
                    COMPARISON.evaluate(self.corpus, [data])
        with self.assertRaises(ValueError):
            COMPARISON.evaluate(self.corpus, [self.oracle(), self.oracle()])

    def test_usage_rejects_nonfinite_negative_and_boolean_values(self):
        for field, value in (("cost_usd", float("nan")), ("elapsed_seconds", float("inf")),
                             ("cost_usd", -1), ("input_tokens", True), ("output_tokens", 1.5)):
            with self.subTest(field=field, value=value):
                data = self.oracle()
                data["usage"] = {field: value}
                with self.assertRaises(ValueError):
                    COMPARISON.validate_predictions(data, self.packet)

    def test_portable_fixture_paths_cannot_escape_or_alias(self):
        for path in ("../AGENTS.md", "C:/AGENTS.md", "\\AGENTS.md", "/AGENTS.md", "./AGENTS.md",
                     "a//AGENTS.md", "a/../AGENTS.md", "file:stream", "CON.txt", "a. /file", "a/AGENTS.md."):
            with self.subTest(path=path), self.assertRaises(ValueError):
                COMPARISON._fixture_path(path)
        self.assertEqual(COMPARISON._fixture_path("package/local guide.md"), Path("package/local guide.md"))

    def test_duplicate_snapshots_and_path_conflicts_are_rejected(self):
        data = copy.deepcopy(self.corpus)
        data["cases"][1]["files"] = data["cases"][0]["files"]
        with self.assertRaisesRegex(ValueError, "duplicate input"):
            self.load_modified(data)
        for files in ({"AGENTS.md": "x", "agents.md": "y"}, {"package": "x", "package/AGENTS.md": "y"}):
            data = copy.deepcopy(self.corpus)
            data["cases"][0]["files"] = files
            with self.assertRaises(ValueError):
                self.load_modified(data)

    def test_known_or_provisional_inputs_cannot_be_rebranded_holdout(self):
        data = copy.deepcopy(self.corpus)
        data["tier"] = "holdout"
        with self.assertRaisesRegex(ValueError, "holdout requires"):
            self.load_modified(data)
        data.update(used_for_rule_development=False, label_status="adjudicated")
        with self.assertRaises(ValueError):
            self.load_modified(data)

    def test_malformed_manifest_values_are_actionable_errors(self):
        for key, value in (("tier", []), ("label_status", {}), ("labelers", []),
                           ("used_for_rule_development", "false"), ("schema_version", True)):
            data = copy.deepcopy(self.corpus)
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.load_modified(data)
        for key, value in (("label", []), ("source_kind", {}), ("id", None)):
            data = copy.deepcopy(self.corpus)
            data["cases"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.load_modified(data)

    def test_holdout_attestations_are_checked_but_not_certified(self):
        # Validation of declarations is not a claim that these synthetic test
        # inputs actually qualify as a held-out, independently labeled dataset.
        data = copy.deepcopy(self.corpus)
        data.update(tier="holdout", used_for_rule_development=False, label_status="adjudicated",
                    labelers=["Fixture rater A", "Fixture rater B"])
        accepted = self.load_modified(data)
        self.assertIn("dataset-owner declaration", COMPARISON.markdown_report(COMPARISON.evaluate(accepted, [])))
        data["labelers"] = ["Fixture rater A", " fixture RATER a "]
        with self.assertRaises(ValueError):
            self.load_modified(data)

    def test_zero_recall_f1_is_zero_and_undefined_precision_is_not_one(self):
        values = COMPARISON.metrics([{"id": "a", "label": "review"}], {"a": False})
        self.assertEqual(values["recall"], 0.0)
        self.assertEqual(values["f1"], 0.0)
        self.assertIsNone(values["precision"])
        values = COMPARISON.metrics([{"id": "a", "label": "unresolved"}], {})
        self.assertEqual(values["status"], "no_reference_labels")
        self.assertIsNone(values["f1"])

    def test_report_does_not_render_external_markup_from_reviewer_name(self):
        data = self.oracle()
        data["reviewer"] = '<img src="https://example.com/track"> ![x](https://example.com/track) | model'
        rendered = COMPARISON.markdown_report(COMPARISON.evaluate(self.corpus, [data]))
        self.assertNotIn("<img", rendered)
        self.assertNotIn("![x]", rendered)
        self.assertIn("\\| model", rendered)

    def test_cli_exports_locally_scores_and_refuses_overwrites(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")

        def run(*args):
            return subprocess.run([sys.executable, str(RUNNER), *args], cwd=ROOT, env=environment,
                                  text=True, encoding="utf-8", errors="replace", capture_output=True)

        self.assertEqual(run("--help").returncode, 0)
        with tempfile.TemporaryDirectory() as directory:
            exported = Path(directory) / "export"
            self.assertEqual(run("export", "--output-dir", str(exported)).returncode, 0)
            packet = json.loads((exported / "review-packet.json").read_text(encoding="utf-8"))
            self.assertEqual(packet, self.packet)
            template = json.loads((exported / "predictions-template.json").read_text(encoding="utf-8"))
            with self.assertRaises(ValueError):
                COMPARISON.validate_predictions(template, packet)
            self.assertNotEqual(run("export", "--output-dir", str(exported)).returncode, 0)
            output, report = Path(directory) / "result.json", Path(directory) / "result.md"
            self.assertEqual(run("score", "--output", str(output), "--markdown", str(report)).returncode, 0)
            before = output.read_bytes()
            self.assertNotEqual(run("score", "--output", str(output)).returncode, 0)
            self.assertEqual(output.read_bytes(), before)
            self.assertIn("not run", report.read_text(encoding="utf-8"))
            self.assertIn("Nothing was uploaded", run("export", "--output-dir", str(Path(directory) / "another")).stdout)


if __name__ == "__main__":
    unittest.main()
