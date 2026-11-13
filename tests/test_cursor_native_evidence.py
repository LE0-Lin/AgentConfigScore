import copy
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_evidence", ROOT / "scripts/verify_cursor_native_evidence.py")
EVIDENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVIDENCE)


class NativeEvidenceTests(unittest.TestCase):
    def inputs(self):
        base = EVIDENCE.BASE
        return (EVIDENCE.load(base / "prepared-inputs.json"), EVIDENCE.load(base / "observations.json"),
                [json.loads(s) for s in (base / "behavior-events.jsonl").read_text(encoding="utf-8").splitlines()])

    def test_retained_evidence_is_reproducible_without_native_client_or_model(self):
        result = EVIDENCE.verify(EVIDENCE.BASE)
        self.assertEqual(result["automatic_visible_marker_set_matches"], 4)
        self.assertEqual(result["native_cases"], 5)
        self.assertFalse(result["independent_accuracy_established"])
        self.assertIsNone(result["general_accuracy_percentage"])

    def test_nonmatching_behavior_remains_a_completed_observation(self):
        prepared, observed, events = self.inputs()
        observed = copy.deepcopy(observed)
        observed["cases"][0]["visible_final_excerpt"] = "health"
        observed["cases"][0]["observed_visible_markers"] = []
        result = EVIDENCE.assess(prepared, observed, events)
        self.assertEqual(result["status"], "retained_evidence_verified")
        self.assertEqual(result["automatic_visible_marker_set_matches"], 3)

    def test_misattributed_case_and_unreported_extra_marker_are_rejected(self):
        for mutation in ("session", "marker"):
            prepared, observed, events = self.inputs()
            if mutation == "session":
                observed["cases"][1]["conversation_id_sha256"] = observed["cases"][0]["conversation_id_sha256"]
            else:
                observed["cases"][0]["visible_final_excerpt"] += " ACS_FAKE_0000000000000000"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                EVIDENCE.assess(prepared, observed, events)


if __name__ == "__main__":
    unittest.main()
