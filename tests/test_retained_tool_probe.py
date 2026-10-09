import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_review_comparison import _digest, load_corpus


class RetainedToolProbeTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / "benchmarks" / "prospective-review-v1"
        self.record = self.read("tool-probe/replay-20261009.json")
        self.report = self.read("tool-probe/report.json")
        self.protocol = self.read("tool-probe/replay-protocol.json")

    def read(self, name):
        return json.loads((self.base / name).read_text(encoding="utf-8"))

    def test_retained_report_and_protocol_are_bound_to_original_inputs(self):
        self.assertEqual(_digest(self.report), self.record["report_normalized_json_sha256"])
        self.assertEqual(_digest(self.protocol), self.record["protocol_normalized_json_sha256"])
        self.assertEqual(self.protocol, self.read("tool-probe-protocol.json"))
        self.assertEqual(_digest(self.read("tool-probe/failures.json")),
                         self.record["prior_failures_normalized_json_sha256"])
        for key in ("packet_sha256", "context_corpus_sha256", "tool_source_sha256"):
            self.assertEqual(self.report[key], self.protocol[key])
        self.assertEqual(self.report["protocol_sha256"], _digest(self.protocol))
        self.assertEqual(self.report["packet_sha256"], self.read("pilot/review-packet.json")["packet_sha256"])
        self.assertEqual(self.report["context_corpus_sha256"],
                         _digest(load_corpus(self.base / "context" / "corpus.json")))

    def test_snapshot_membership_counts_and_declared_limits_remain_consistent(self):
        snapshot = self.report["snapshot"]
        total = sum(snapshot[key] for key in ("regular_files", "directories", "symlinks"))
        self.assertEqual(total, snapshot["tree_entries"])
        self.assertEqual(snapshot["tree_entries"], 50749)
        self.assertEqual(snapshot["canonical_tree_object_sha"], self.protocol["canonical_tree_object_sha"])
        self.assertEqual(self.report["archive"]["archive_bytes"], 51988413)
        self.assertLessEqual(self.report["archive"]["archive_bytes"], self.protocol["maximum_archive_bytes"])
        self.assertLessEqual(snapshot["verified_blob_bytes"], self.protocol["maximum_source_bytes"])
        self.assertEqual(self.report["input_verification"]["supplied_files_verified"], 11)
        self.assertEqual(self.report["input_verification"]["physical_path_facts_checked"], 420)
        self.assertEqual(self.report["input_verification"]["unknown_path_facts_not_asserted"], 36)

    def test_unscored_scope_observations_never_become_correctness_metrics(self):
        self.assertEqual(self.report["status"], "actual_tool_probe_unscored")
        self.assertEqual(self.report["package_version"], "0.22.0")
        self.assertEqual(self.report["host_platform"], "Linux")
        self.assertFalse(self.report["comparison_ready"])
        self.assertIsNone(self.report["correctness_metrics"])
        self.assertEqual(self.report["human_reference_status"], "unreviewed")
        self.assertEqual(self.report["hybrid_status"], "not_run")
        self.assertEqual(len(self.report["native_discovery"]["files"]), 27)
        self.assertEqual(self.report["root_instruction_scope"]["files"], ["AGENTS.md"])
        for scope in ("native_discovery", "root_instruction_scope"):
            observation = self.report[scope]
            self.assertEqual(len(observation["findings"]), 9)
            self.assertNotIn("root", observation)
            self.assertTrue(observation["review_needed"])
        self.assertIsNone(self.record["correctness_metrics"])
        self.assertFalse(self.record["comparison_ready"])
        self.assertEqual([attempt["completed_scans"] for attempt in self.record["attempts"]], [0, 0, 0, 1])
        self.assertFalse(self.record["attempts"][2]["changed_case_or_protocol"])


if __name__ == "__main__":
    unittest.main()
