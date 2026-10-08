import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

from agent_config_score.initializer import CONFIG_CONTENT


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_VARIANTS = ("simplified", "traditional")


def blocks(text, language):
    return re.findall(r"```" + re.escape(language) + r"\n(.*?)\n```", text, re.DOTALL)


class DocumentationLanguageTests(unittest.TestCase):
    def test_english_stays_the_default_package_readme(self):
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('readme = "README.md"', project)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("English |", readme)
        for variant in SCRIPT_VARIANTS:
            self.assertIn(f"README.{variant}.md", readme)
            page = (ROOT / f"README.{variant}.md").read_text(encoding="utf-8")
            self.assertIn("[English](README.md)", page)
            self.assertIn(f"docs/{variant}/user-guide.md", page)
            self.assertIn(f"docs/{variant}/limitations.md", page)

    def test_localized_guides_preserve_every_english_executable_example(self):
        source = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
        expected = blocks(source, "bash")
        self.assertGreater(len(expected), 5)
        for variant in SCRIPT_VARIANTS:
            with self.subTest(variant=variant):
                page = (ROOT / "docs" / variant / "user-guide.md").read_text(encoding="utf-8")
                self.assertEqual(blocks(page, "bash"), expected)
                for code in ("--max-drop", "--fail-on-new-errors", "--json", "--sarif", "--force"):
                    self.assertIn(code, page)

    def test_overviews_use_the_same_commands_config_and_workflow(self):
        pages = [(ROOT / f"README.{variant}.md").read_text(encoding="utf-8") for variant in SCRIPT_VARIANTS]
        for language in ("bash", "json", "yaml"):
            with self.subTest(language=language):
                self.assertEqual(blocks(pages[0], language), blocks(pages[1], language))
                self.assertTrue(blocks(pages[0], language))
        self.assertEqual(json.loads(blocks(pages[0], "json")[0]), json.loads(CONFIG_CONTENT))
        workflow = blocks(pages[0], "yaml")[0]
        self.assertIn("contents: read", workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("LE0-Lin/AgentConfigScore@v0.23.0", workflow)

    def test_localized_links_target_real_files_inside_the_repository(self):
        paths = [ROOT / f"README.{variant}.md" for variant in SCRIPT_VARIANTS]
        paths += [ROOT / "docs" / variant / name for variant in SCRIPT_VARIANTS
                  for name in ("user-guide.md", "limitations.md")]
        paths += [ROOT / "README.md"]
        paths += [ROOT / "docs" / name for name in
                  ("README.md", "user-guide.md", "limitations.md", "translations.md",
                   "release-readiness.md")]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for destination in re.findall(r"!?\[[^\]\n]+\]\(([^)\n]+)\)", text):
                parts = urlsplit(destination)
                if parts.scheme or not parts.path:
                    continue
                target = (path.parent / unquote(parts.path)).resolve()
                with self.subTest(page=path.name, destination=destination):
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.is_file(), target)

    def test_core_limits_keep_stable_rule_ids_and_source_scope_visible(self):
        for variant in SCRIPT_VARIANTS:
            page = (ROOT / "docs" / variant / "limitations.md").read_text(encoding="utf-8")
            for code in ("rm-rf", "prompt-injection-override", "false-success-report",
                         "broad-environment-upload", "no-config", "empty-instructions",
                         "instruction-file-removed", "directive-polarity-flip"):
                self.assertIn(code, page)
            self.assertIn("A 100", page)
            self.assertIn("474/474", page)
            self.assertIn("6/8", page)
            self.assertIn("../translations.md", page)
        note = (ROOT / "docs" / "translations.md").read_text(encoding="utf-8")
        self.assertIn("78af3f9a470c9edab67f3d1579e8319a299bb191", note)
        self.assertIn("cannot verify translation meaning", note)
        self.assertIn("Advanced Action inputs/outputs", note)


if __name__ == "__main__":
    unittest.main()
