"""Method checks for the optional study, outside dependency-free runtime tests."""
import unittest

from run_link_study import document_names, local_target, reference_cases


def tree(*names):
    return {"tree": [{"path": name, "type": "blob", "mode": "100644"} for name in names]}


class ReferenceChecks(unittest.TestCase):
    def test_fenced_and_inline_code_are_not_links(self):
        text = "```md\n[x](missing.md)\n```\n\n`[x](also-missing.md)`\n\n[x](real.md)\n"
        cases, _ = reference_cases(text, "AGENTS.md", tree("real.md"))
        self.assertEqual([(row["destination"], row["line"], row["target_exists"]) for row in cases],
                         [("real.md", 7, True)])

    def test_reference_url_decoding_and_duplicate_use(self):
        text = "[one][guide]\n\n[two](a%20b.md#section)\n\n[guide]: a%20b.md?mode=1\n"
        cases, excluded = reference_cases(text, "AGENTS.md", tree("a b.md"))
        self.assertEqual(len(cases), 1)
        self.assertTrue(cases[0]["target_exists"])
        self.assertEqual(cases[0]["destination"], "a b.md")
        self.assertEqual(excluded[0]["excluded"], "duplicate_document_destination")

    def test_document_relative_semantics_differ_from_root_fallback(self):
        index = {row["path"]: row for row in tree("guide.md")["tree"]}
        result = local_target("guide.md", "nested/AGENTS.md", index)
        self.assertFalse(result["target_exists"])
        self.assertEqual(result["resolved_target"], "nested/guide.md")
        self.assertTrue(local_target("../guide.md", "nested/AGENTS.md", index)["target_exists"])

    def test_aliases_and_traversal_abstain(self):
        index = {"alias": {"type": "blob", "mode": "120000"},
                 "vendor": {"type": "commit", "mode": "160000"}}
        for path in ("alias/a.md", "vendor/README.md"):
            self.assertEqual(local_target(path, "AGENTS.md", index)["excluded"],
                             "symlink_or_gitlink_dependency")
        self.assertEqual(local_target("../outside.md", "AGENTS.md", {})["excluded"], "out_of_root")

    def test_multiline_blocks_are_declared_exclusions(self):
        cases, excluded = reference_cases("See [guide](guide.md)\nfor details.\n", "AGENTS.md", tree("guide.md"))
        self.assertEqual(cases, [])
        self.assertEqual(excluded[0]["excluded"], "multiline_inline_block")

    def test_selection_has_fixed_priority_and_no_symlink_documents(self):
        value = tree("z/AGENTS.md", "AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md", "a/AGENTS.md")
        value["tree"].append({"path": "b/AGENTS.md", "type": "blob", "mode": "120000"})
        self.assertEqual(document_names(value, 4),
                         ["AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md", "a/AGENTS.md"])


if __name__ == "__main__":
    unittest.main()
