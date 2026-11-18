import tempfile
import unittest
from pathlib import Path

from agent_config_score.regression import compare
from agent_config_score.scanner import analyze


def scan(text):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "AGENTS.md").write_text(text, encoding="utf-8")
        return [row for row in analyze(root).findings if row.code == "dead-path"]


class InlineLinkExampleTests(unittest.TestCase):
    def test_inline_code_is_an_example_not_a_link(self):
        for text in (
            "Use `[Guide](docs/missing.md)` as syntax.\n",
            "Use ``[Guide](docs/missing.md)`` as syntax.\n",
            "Use `![Image](assets/missing.png)` as syntax.\n",
            "A multiline code span: `[Guide](docs/missing.md)\ncontinues here`.\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text), [])

    def test_escaped_opening_bracket_is_not_a_link(self):
        for text in (
            r"\[Guide](docs/missing.md)",
            r"!\[Image](assets/missing.png)",
            r"\[Guide](docs/missing.md 'Guide')",
            r"\[Guide](docs/missing.md (Guide))",
        ):
            with self.subTest(text=text):
                self.assertEqual(scan(text + "\n"), [])

    def test_inline_links_support_single_quoted_and_parenthesized_titles(self):
        for text in (
            "[Guide](CONTRIBUTING.md 'Guide')\n",
            "[Guide](CONTRIBUTING.md (Guide))\n",
            "[Guide](<local guide.md> 'Guide')\n",
        ):
            with self.subTest(text=text):
                findings = scan(text)
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0].line, 1)

    def test_actual_links_remain_visible_beside_code_and_escapes(self):
        for text in (
            "`[Example](docs/example.md)` and [Real](docs/missing.md).\n",
            "[Read `guide`](docs/missing.md)\n",
            "`Unclosed span [Real](docs/missing.md)\n",
            r"\\[Real](docs/missing.md)" + "\n",
            r"\![Real](docs/missing.md)" + "\n",
        ):
            with self.subTest(text=text):
                self.assertEqual([(row.line, row.message) for row in scan(text)],
                                 [(1, "Referenced path does not exist: docs/missing.md")])

    def test_removing_example_wrapper_is_a_real_regression(self):
        with tempfile.TemporaryDirectory() as directory:
            base, head = Path(directory) / "base", Path(directory) / "head"
            base.mkdir()
            head.mkdir()
            (base / "AGENTS.md").write_text("`[Guide](docs/missing.md)`\n", encoding="utf-8")
            (head / "AGENTS.md").write_text("[Guide](docs/missing.md)\n", encoding="utf-8")
            report = compare(base, head)
            self.assertFalse(report.base.findings)
            self.assertEqual([row.code for row in report.new_findings], ["dead-path"])


if __name__ == "__main__":
    unittest.main()
