from pathlib import Path
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
        for tool in self.EXAMPLES:
            with self.subTest(tool=tool):
                report = analyze(ROOT / "examples" / tool)
                self.assertEqual(report.grade, "A")
                self.assertFalse(report.findings)

    def test_cursor_example_uses_project_rules_instead_of_legacy_cursorrules(self):
        cursor_root = ROOT / "examples" / "cursor"
        self.assertFalse((cursor_root / ".cursorrules").exists())
        text = (cursor_root / ".cursor" / "rules" / "project.mdc").read_text(encoding="utf-8")
        self.assertIn("alwaysApply: true", text)


if __name__ == "__main__":
    unittest.main()
