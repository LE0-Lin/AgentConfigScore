import hashlib
import json
from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_review_comparison import _digest, load_corpus, review_packet


class HumanReviewPreparationTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / "benchmarks" / "prospective-review-v1"
        self.corpus = load_corpus(self.base / "context" / "corpus.json")
        self.protocol = json.loads((self.base / "human-pilot" / "protocol.json").read_text(encoding="utf-8"))
        self.case = next(case for case in self.corpus["cases"]
                         if case["id"] == self.protocol["selected_case_id"])

    def test_readable_source_matches_retained_bytes_and_packet(self):
        page = (self.base / "human-pilot" / "review.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```markdown\n(.*?)\n```", page, re.DOTALL)
        self.assertEqual(len(blocks), 1)
        source = blocks[0] + "\n"
        self.assertEqual(self.case["files"], {"AGENTS.md": source})
        self.assertEqual(len(source.splitlines()), 28)
        self.assertEqual(hashlib.sha256(source.encode("utf-8")).hexdigest(),
                         self.protocol["source_sha256"])
        packet = review_packet({**self.corpus, "cases": [self.case]})
        self.assertEqual(packet["packet_sha256"], self.protocol["canonical_packet_sha256"])
        self.assertEqual(packet["cases"][0]["id"], self.protocol["opaque_case_id"])
        self.assertIn(self.protocol["opaque_case_id"], page)
        self.assertEqual(self.case["repository_context"]["tracked_path_facts"], [])
        self.assertEqual(self.case["repository_context"]["omitted_documents"], [])

    def test_shortest_input_selection_preserves_frozen_unreviewed_parent(self):
        sizes = sorted((sum(len(text.encode("utf-8")) for text in case["files"].values()), case["id"])
                       for case in self.corpus["cases"])
        self.assertEqual(sizes[0], (self.protocol["selected_text_bytes"], self.case["id"]))
        self.assertEqual(_digest(self.corpus), self.protocol["parent_corpus_sha256"])
        self.assertEqual(self.corpus["tier"], "candidate")
        self.assertEqual(self.corpus["label_status"], "unreviewed")
        self.assertEqual(self.corpus["labelers"], [])
        self.assertTrue(all(case["label"] == "unresolved" for case in self.corpus["cases"]))

    def test_consent_and_preparation_do_not_become_completed_evaluation(self):
        self.assertEqual(self.protocol["annotation_status"], "awaiting_annotation")
        self.assertEqual(self.protocol["annotations"], [])
        self.assertEqual(self.protocol["tool_predictions"], "not_run_for_this_case")
        self.assertEqual(self.protocol["model_predictions"], "not_run_for_this_case")
        self.assertIsNone(self.protocol["correctness_metrics"])
        page = (self.base / "human-pilot" / "review.md").read_text(encoding="utf-8")
        self.assertIn("同意审阅不算已完成标注", page)
        self.assertIn("不要运行其中的命令", page)


if __name__ == "__main__":
    unittest.main()
