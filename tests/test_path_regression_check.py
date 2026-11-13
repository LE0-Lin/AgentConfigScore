import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("path_regression_check", ROOT / "scripts/run_path_regression_check.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class PathRegressionCheckTests(unittest.TestCase):
    def data(self):
        return {"known_generated_output": {"current_flagged": False},
                "known_controls": [{"id": "directory", "target_kind": "tree", "destination": "./src/", "current_flagged": True},
                                   {"id": "file", "target_kind": "blob", "destination": "guide.md", "current_flagged": True},
                                   {"id": "unresolved-name", "target_kind": "tree", "destination": "test/unit", "current_flagged": False}],
                "explicit_directory_variants": [{"parent_control": "variant", "current_flagged": True}],
                "new_whole_document_warnings": [],
                "known_natural_cases": [{"id": "negative", "provisional_review_needed": False, "current_flagged": False}]}

    def test_known_development_gate_retains_limit_without_requiring_miss(self):
        data = self.data()
        self.assertTrue(CHECK.acceptance(data)["passed"])
        data["known_controls"][2]["current_flagged"] = True
        self.assertTrue(CHECK.acceptance(data)["passed"])

    def test_returning_generated_false_positive_or_missing_required_control_fails(self):
        for kind in ("generated", "directory", "file", "negative", "variant", "unselected"):
            with self.subTest(kind=kind):
                data = self.data()
                if kind == "generated":
                    data["known_generated_output"]["current_flagged"] = True
                elif kind == "negative":
                    data["known_natural_cases"][0]["current_flagged"] = True
                elif kind == "variant":
                    data["explicit_directory_variants"][0]["current_flagged"] = False
                elif kind == "unselected":
                    data["new_whole_document_warnings"].append({"repository": "owner/project", "line": 97})
                else:
                    data["known_controls"][0 if kind == "directory" else 1]["current_flagged"] = False
                self.assertFalse(CHECK.acceptance(data)["passed"])

    def test_fresh_collection_is_verified_without_inventing_positive_labels(self):
        protocol, collection, trees = CHECK.fresh_inputs()
        self.assertEqual(protocol["status"], "fresh_source_smoke_not_independent_accuracy")
        self.assertEqual(collection["selected_cases"], 0)
        self.assertEqual(len(trees), 1)
        self.assertEqual(len(collection["repositories"]), 3)
        self.assertTrue(all("review_needed" not in row for row in collection["repositories"]))

    def test_retained_reports_preserve_failures_and_separate_variant_counts(self):
        evidence = json.loads((CHECK.FRESH / "evidence.json").read_text(encoding="utf-8"))
        for name, digest in evidence["reports"].items():
            self.assertEqual(hashlib.sha256((CHECK.FRESH / name).read_bytes()).hexdigest(), digest)
        result = json.loads((CHECK.FRESH / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(CHECK.acceptance(result), result["acceptance"])
        self.assertTrue(result["acceptance"]["passed"])
        self.assertFalse(result["fresh_parser_matches_collection_freeze"])
        self.assertEqual(sum(r["current_flagged"] for r in result["known_controls"]), 3)
        self.assertEqual(len(result["explicit_directory_variants"]), 4)
        self.assertTrue(all(r["current_flagged"] for r in result["explicit_directory_variants"]))
        self.assertEqual(result["new_whole_document_warnings"], [])
        failed = json.loads((CHECK.FRESH / "first-attempt.json").read_text(encoding="utf-8"))
        self.assertFalse(failed["acceptance"]["passed"])
        self.assertIn("known_natural_negative_flagged:path-11", failed["acceptance"]["failures"])


if __name__ == "__main__":
    unittest.main()
