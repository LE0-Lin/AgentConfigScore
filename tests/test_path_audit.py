import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("path_audit", ROOT / "scripts/run_path_audit.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class PathAuditTests(unittest.TestCase):
    def test_retained_inputs_match_full_git_trees_and_provisional_labels(self):
        protocol, controls, collection, labels, trees = AUDIT.verify_inputs(AUDIT.BASE)
        self.assertEqual(protocol["product_version"], "0.26.1")
        self.assertEqual(controls["cases"], 8)
        self.assertEqual(collection["selected_cases"], 16)
        self.assertEqual(len(labels), 16)
        self.assertEqual(len(trees), 6)

    def test_unsafe_projection_paths_are_rejected(self):
        for path in ("/outside", "../outside", "a/../outside", "a\\outside", "C:/outside", ".Git/config"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                AUDIT.portable(path)

    def test_projection_preserves_source_omits_mutation_and_does_not_follow_links(self):
        tree = {"tree": [
            {"path": "AGENTS.md", "type": "blob", "mode": "100644"},
            {"path": "src", "type": "tree", "mode": "040000"},
            {"path": "src/tool.py", "type": "blob", "mode": "100755"},
            {"path": "alias", "type": "blob", "mode": "120000"},
        ]}
        source = b"Read `src/tool.py`.\n"
        for omitted in (None, "src"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                evidence = AUDIT.projection(root, tree, "AGENTS.md", source, omitted)
                self.assertEqual((root / "AGENTS.md").read_bytes(), source)
                self.assertEqual((root / "src/tool.py").exists(), omitted is None)
                if omitted is None:
                    self.assertEqual((root / "src/tool.py").read_bytes(), b"")
                self.assertFalse((root / "alias").exists())
                self.assertEqual(evidence["skipped_aliases_or_gitlinks"], ["alias"])

    def test_predictions_match_literal_and_line_not_another_finding_on_same_line(self):
        findings = [{"line": 7, "message": "Referenced path does not exist: other.md"}]
        self.assertFalse(AUDIT.flagged(findings, {"line": 7, "destination": "wanted.md"}))
        self.assertFalse(AUDIT.flagged(findings, {"line": 8, "destination": "other.md"}))
        self.assertTrue(AUDIT.flagged(findings, {"line": 7, "destination": "other.md"}))

    def test_unresolved_observations_are_never_clean_counts(self):
        result = AUDIT.counts([
            {"review_needed": None, "tool_flagged": False},
            {"review_needed": True, "tool_flagged": False},
            {"review_needed": False, "tool_flagged": True},
        ])
        self.assertEqual(result["unresolved"], 1)
        self.assertEqual(result["false_negative"], 1)
        self.assertEqual(result["false_positive"], 1)
        self.assertEqual(result["true_negative"], 0)


if __name__ == "__main__":
    unittest.main()
