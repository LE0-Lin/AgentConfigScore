from pathlib import Path
import tempfile
import unittest

from agent_config_score.scanner import analyze


ROOT = Path(__file__).resolve().parents[1]


class CopyReadyExampleTests(unittest.TestCase):
    EXAMPLES = {
        "cursor": ".cursor/rules/project.mdc",
        "copilot": ".github/copilot-instructions.md",
        "gemini": "GEMINI.md",
        "claude-code": "CLAUDE.md",
    }

    def test_each_tool_has_a_nonempty_copy_target(self):
        for tool, rel in self.EXAMPLES.items():
            with self.subTest(tool=tool):
                path = ROOT / "examples" / tool / rel
                self.assertTrue(path.is_file())
                self.assertGreater(len(path.read_text(encoding="utf-8").split()), 40)

    def test_each_template_scans_without_active_findings(self):
        for tool, rel in self.EXAMPLES.items():
            with self.subTest(tool=tool):
                source = ROOT / "examples" / tool / rel
                with tempfile.TemporaryDirectory() as d:
                    target = Path(d) / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
                    report = analyze(Path(d))
                    self.assertEqual(report.grade, "A")
                    self.assertFalse(report.findings)

    def test_cursor_example_uses_project_rules_instead_of_legacy_cursorrules(self):
        cursor_root = ROOT / "examples" / "cursor"
        text = (cursor_root / ".cursor" / "rules" / "project.mdc").read_text(encoding="utf-8")
        self.assertIn("alwaysApply: true", text)
        self.assertGreater(len(text), len((cursor_root / ".cursorrules").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
