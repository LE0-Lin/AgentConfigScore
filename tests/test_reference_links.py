"""Bounded Markdown reference-link contracts, not full Markdown conformance."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from agent_config_score.entrypoint import main
from agent_config_score.regression import compare
from agent_config_score.scanner import analyze


FORMATS = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules",
           ".github/copilot-instructions.md", ".cursor/rules/review.mdc")


class ReferenceLinkTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()

    def scan(self, text, filename="AGENTS.md", existing=()):
        for name in existing:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("source\n", encoding="utf-8")
        source = self.root / filename
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(text.encode("utf-8"))
        return analyze(self.root)

    def dead(self, text, **kwargs):
        return [(f.line, f.message) for f in self.scan(text, **kwargs).findings if f.code == "dead-path"]

    def test_missing_full_reference_is_reported_at_definition_in_all_formats(self):
        for filename in FORMATS:
            with self.subTest(filename=filename):
                # Separate roots so other formats cannot introduce duplicates.
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = root / filename
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_text("Read [build guide][setup].\n\n[setup]: BUILD.md\n", encoding="utf-8")
                    dead = [f for f in analyze(root).findings if f.code == "dead-path"]
                    self.assertEqual([(f.file, f.line, f.message) for f in dead],
                                     [(filename, 3, "Referenced path does not exist: BUILD.md")])

    def test_existing_targets_and_collapsed_references(self):
        self.assertEqual(self.dead("Read [Guide][] and [setup][build].\n\n"
                                   "[Guide]: GUIDE.md\n[build]: BUILD.md\n",
                                   existing=("GUIDE.md", "BUILD.md")), [])
        self.assertEqual(self.dead("Read [Guide][].\n\n[guide]: ABSENT.md\n"),
                         [(3, "Referenced path does not exist: ABSENT.md")])

    def test_label_case_and_ascii_whitespace_normalization(self):
        self.assertEqual(self.dead("Read [build][  BUILD\t GUIDE  ].\n\n"
                                   "[build guide]: ABSENT.md\n"),
                         [(3, "Referenced path does not exist: ABSENT.md")])
        self.assertEqual(self.dead("Read [guide][STRASSE].\n\n[straße]: ABSENT.md\n"),
                         [(3, "Referenced path does not exist: ABSENT.md")])

    def test_definitions_can_precede_uses_and_repeated_uses_report_once(self):
        self.assertEqual(self.dead("[guide]: ABSENT.md\n\nRead [one][guide] and [two][guide].\n"
                                   "Read [three][guide].\n"),
                         [(1, "Referenced path does not exist: ABSENT.md")])

    def test_first_definition_wins_even_if_external_or_anchor_only(self):
        for destination in ("GUIDE.md", "https://example.invalid/guide", "#guide"):
            with self.subTest(destination=destination):
                self.assertEqual(self.dead(f"Read [guide][setup].\n\n[setup]: {destination}\n"
                                           "[SETUP]: docs/absent.md\n", existing=("GUIDE.md",)), [])
        self.assertEqual(self.dead("Read [guide][setup].\n\n[setup]: ABSENT.md\n"
                                   "[setup]: GUIDE.md\n", existing=("GUIDE.md",)),
                         [(3, "Referenced path does not exist: ABSENT.md")])

    def test_unused_definitions_and_undefined_or_shortcut_labels_are_not_checked(self):
        self.assertEqual(self.dead("Read [guide][undefined] or [shortcut].\n\n"
                                   "[unused]: docs/absent.md\n[shortcut]: UNUSED.md\n"), [])

    def test_targets_are_document_relative_not_root_or_suffix_relative(self):
        self.assertEqual(self.dead("Read [guide][setup].\n\n[setup]: GUIDE.md\n",
                                   filename=".github/copilot-instructions.md", existing=("GUIDE.md",)),
                         [(3, "Referenced path does not exist: GUIDE.md")])
        self.assertEqual(self.dead("Read [guide][setup].\n\n[setup]: ../GUIDE.md\n",
                                   filename=".github/copilot-instructions.md", existing=("GUIDE.md",)), [])

    def test_angles_encoded_spaces_fragments_and_single_line_titles(self):
        for target in ('<docs/My Guide.md#setup> "Build guide"',
                       "docs/My%20Guide.md?view=1#setup 'Build guide'",
                       'docs/My%20Guide.md (Build guide)'):
            with self.subTest(target=target):
                self.assertEqual(self.dead(f"Read [guide][setup].\n\n[setup]: {target}\n",
                                           existing=("docs/My Guide.md",)), [])
        self.assertEqual(self.dead("Read [guide][setup].\n\n[setup]: <My Missing.md>\n"),
                         [(3, "Referenced path does not exist: My Missing.md")])

    def test_reference_images_and_display_text_are_not_extra_prose_paths(self):
        self.assertEqual(self.dead("![diagram][image]\nRead [`src/display.py`][guide].\n\n"
                                   "[image]: diagram.svg\n[guide]: GUIDE.md\n", existing=("GUIDE.md",)),
                         [(4, "Referenced path does not exist: diagram.svg")])

    def test_fenced_and_inline_code_do_not_activate_references(self):
        for fence in ("```", "~~~"):
            with self.subTest(fence=fence):
                self.assertEqual(self.dead(f"{fence}md\nRead [guide][setup].\n{fence}\n\n"
                                           "[setup]: ABSENT.md\n"), [])
                self.assertEqual(self.dead(f"Read [guide][setup].\n\n{fence}\n"
                                           f"[setup]: ABSENT.md\n{fence}\n"), [])
        self.assertEqual(self.dead("`[guide][setup]` and ``[guide][setup]``.\n\n"
                                   "[setup]: ABSENT.md\n"), [])
        self.assertEqual(self.dead("`example\n[guide][setup]`\n\n[setup]: ABSENT.md\n"), [])
        self.assertEqual(self.dead("`example` then [guide][setup].\n\n[setup]: ABSENT.md\n"),
                         [(3, "Referenced path does not exist: ABSENT.md")])

    def test_escaped_links_and_inline_link_precedence(self):
        self.assertEqual(self.dead(r"\[guide][setup] and !\[image][setup]." + "\n\n"
                                   "[setup]: ABSENT.md\n"), [])
        self.assertEqual(self.dead("[caption](https://example.invalid/[guide][setup]).\n\n"
                                   "[setup]: ABSENT.md\n"), [])

    def test_external_absolute_template_and_outside_paths_stay_out_of_scope(self):
        for target in ("https://example.invalid/guide", "//example.invalid/guide", "#setup",
                       "/ABSENT.md", "C:/ABSENT.md", "../ABSENT.md", "$ROOT/ABSENT.md",
                       "~/ABSENT.md", "docs/*.md", "docs/{name}.md"):
            with self.subTest(target=target):
                self.assertEqual(self.dead(f"Read [guide][setup].\n\n[setup]: {target}\n"), [])

    def test_ambiguous_definition_shapes_do_not_turn_into_guessed_targets(self):
        for definition in ("    [setup]: ABSENT.md", "[setup]:\n ABSENT.md",
                           '[setup]: ABSENT.md "title" trailing', "[setup]: path(with).md"):
            with self.subTest(definition=definition):
                self.assertEqual(self.dead(f"Read [guide][setup].\n\n{definition}\n"), [])
        # A definition cannot interrupt a paragraph.
        self.assertEqual(self.dead("Read [guide][setup].\n[setup]: ABSENT.md\n"), [])

    def test_html_layouts_decline_new_reference_interpretation(self):
        for markup in ("<!--\n[guide][setup]\n-->", "<pre>[guide][setup]</pre>",
                       '<span title="[guide][setup]">Example</span>'):
            with self.subTest(markup=markup):
                self.assertEqual(self.dead(f"{markup}\n\n[setup]: ABSENT.md\n"), [])

    def test_reference_syntax_never_exempts_independent_danger_checks(self):
        report = self.scan("Run rm -rf cache. Read [guide][setup].\n\n[setup]: GUIDE.md\n",
                           existing=("GUIDE.md",))
        self.assertIn("rm-rf", [f.code for f in report.findings])

    def test_unsupported_first_definition_does_not_select_later_duplicate(self):
        for first in ("[setup]: path(with).md", "> [setup]: GUIDE.md", "- [setup]: GUIDE.md"):
            with self.subTest(first=first):
                self.assertEqual(self.dead(f"Read [guide][setup].\n\n{first}\n\n"
                                           "[setup]: ABSENT.md\n", existing=("GUIDE.md",)), [])

    def test_definition_scope_does_not_cross_instruction_files(self):
        (self.root / "CLAUDE.md").write_text("[setup]: ABSENT.md\n", encoding="utf-8")
        self.assertEqual(self.dead("Read [guide][setup].\n"), [])

    def test_encoded_entities_and_crlf_keep_definition_location(self):
        self.assertEqual(self.dead("Read [guide][setup].\r\n\r\n[setup]: missing&amp;guide.md\r\n"),
                         [(3, "Referenced path does not exist: missing&guide.md")])

    def test_indented_code_and_unclosed_fences_do_not_activate_references(self):
        self.assertEqual(self.dead("    [guide][setup]\n\n[setup]: ABSENT.md\n"), [])
        self.assertEqual(self.dead("```md\n[guide][setup]\n\n[setup]: ABSENT.md\n"), [])

    def test_large_reference_list_is_deduplicated_at_definition_locations(self):
        text = "\n".join(f"Read [guide][ref-{i}]." for i in range(600)) + "\n\n"
        text += "\n".join(f"[ref-{i}]: EXISTING.md" for i in range(600)) + "\n"
        self.assertEqual(self.dead(text, existing=("EXISTING.md",)), [])

    def test_removing_referenced_target_fails_the_baseline_gate_then_fix_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            text = "Read [guide][setup].\n\n[setup]: GUIDE.md\n"
            (base / "AGENTS.md").write_text(text, encoding="utf-8")
            (base / "GUIDE.md").write_text("Guide\n", encoding="utf-8")
            self.scan(text)
            changed = compare(base, self.root)
            self.assertLess(changed.delta, 0)
            self.assertEqual([f.code for f in changed.new_findings], ["dead-path"])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["compare", str(base), str(self.root), "--max-drop", "0"]), 1)
            self.scan(text, existing=("GUIDE.md",))
            self.assertEqual(compare(base, self.root).new_findings, [])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["compare", str(base), str(self.root), "--max-drop", "0"]), 0)

    def test_cli_json_explanations_and_sarif_use_the_definition_location(self):
        self.scan("Read [guide][setup].\n\n[setup]: ABSENT.md\n")
        sarif = self.root / "report.sarif"
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main([str(self.root), "--json", "--explain", "--sarif", str(sarif)])
        self.assertEqual((code, stderr.getvalue()), (0, ""))
        findings = json.loads(stdout.getvalue())["findings"]
        self.assertEqual([(f["code"], f["line"]) for f in findings], [("dead-path", 3)])
        result = json.loads(sarif.read_text(encoding="utf-8"))["runs"][0]["results"][0]
        self.assertEqual(result["locations"][0]["physicalLocation"]["region"]["startLine"], 3)


if __name__ == "__main__":
    unittest.main()
