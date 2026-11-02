import fnmatch
from functools import lru_cache
import itertools
import json
import unittest

from agent_config_score.scopes import ScopeGlob, ScopeInputError, normalize_targets, parse_cursor_rule


FILE = ".cursor/rules/test.mdc"


def rule(fields, body="Always use tabs.\n"):
    return "---\n" + fields + "\n---\n" + body


class ScopeGlobTests(unittest.TestCase):
    def test_documented_patterns_and_segment_boundaries(self):
        cases = (
            ("*.ts", "a.ts", True), ("*.ts", "src/a.ts", False),
            ("**/*.ts", "a.ts", True), ("**/*.ts", "src/a.ts", True),
            ("src/**", "src/a.ts", True), ("src/**", "src/lib/a.ts", True),
            ("src/**", "src", False), ("src/**", "src-other/a.ts", False),
            ("src/**/*.tsx", "src/Button.tsx", True),
            ("src/**/*.tsx", "src/ui/Button.tsx", True),
            ("src/**/*.tsx", "src/ui/Button.ts", False),
            ("a/**/b", "a/b", True), ("a/**/b", "a/x/y/b", True),
            ("**", "a", True), ("**", "x/a", True),
            ("tailwind.config.*", "tailwind.config.ts", True),
            ("src/*/a.ts", "src/x/y/a.ts", False),
            ("src/**", "SRC/a.ts", False), ("*", ".hidden", True),
        )
        for pattern, target, expected in cases:
            with self.subTest(pattern=pattern, target=target):
                self.assertEqual(ScopeGlob.parse(pattern).matches(target), expected)

    def test_iterative_glob_engine_matches_small_recursive_oracle(self):
        @lru_cache(None)
        def oracle(pattern, target):
            if not pattern:
                return not target
            if pattern[0] == "**":
                return oracle(pattern[1:], target) or bool(target and oracle(pattern, target[1:]))
            return bool(target and fnmatch.fnmatchcase(target[0], pattern[0]) and oracle(pattern[1:], target[1:]))

        targets = [parts for size in (1, 2, 3) for parts in itertools.product(("a", "b", "aa"), repeat=size)]
        for size in (1, 2, 3):
            for parts in itertools.product(("a", "b", "*", "a*", "**"), repeat=size):
                model = ScopeGlob.parse("/".join(parts))
                for target in targets:
                    self.assertEqual(model.matches("/".join(target)), oracle(model.segments, target), (parts, target))

    def test_unsupported_glob_language_is_not_assumed_to_match_nothing(self):
        for value in ("", "a//b", "../a", "/a", "./a", "C:/a", "a\\b", "a?", "[ab]", "{a,b}",
                      "!a", "@(a)", "a**b", "a\x00", "a" * 257):
            with self.subTest(value=value), self.assertRaises(ScopeInputError):
                ScopeGlob.parse(value)

    def test_context_paths_are_portable_logical_names_not_probed_files(self):
        self.assertEqual(normalize_targets([r"src\web\a.ts", "./src/web/a.ts", "new/not-created.ts"]),
                         ("new/not-created.ts", "src/web/a.ts"))
        for paths in ([], [".."], ["src/../a"], ["/private/a"], [r"C:\private\a"], ["."], ["x\n"], ["x"] * 65):
            with self.subTest(paths=paths), self.assertRaises(ScopeInputError):
                normalize_targets(paths)


class CursorRuleModelTests(unittest.TestCase):
    def test_always_takes_priority_over_glob_and_description_conditions(self):
        model = parse_cursor_rule(FILE, rule('description: A rule\nglobs: "{unsupported,glob}"\nalwaysApply: true'))
        data = model.activate(("src/a.ts",))
        self.assertEqual((model.mode, data["activation"], data["matched_targets"]), ("always", "active", ["src/a.ts"]))
        self.assertEqual(data["metadata_lines"]["alwaysApply"], 4)
        self.assertEqual(model.body_line, 6)

    def test_scalar_csv_globs_have_or_semantics(self):
        model = parse_cursor_rule(FILE, rule('globs: "src/**/*.ts, tests/**/*.ts"\nalwaysApply: false'))
        data = model.activate(("src/a.ts", "tests/deep/test.ts", "docs/a.ts"))
        self.assertEqual(data["matched_targets"], ["src/a.ts", "tests/deep/test.ts"])
        self.assertEqual(model.activate(("docs/a.ts",))["activation"], "inactive")

    def test_manual_and_agent_selected_modes_stay_unknown(self):
        for fields, mode in (("alwaysApply: false", "manual"),
                             ("description: Backend security review\nalwaysApply: false", "agent_selected")):
            with self.subTest(mode=mode):
                model = parse_cursor_rule(FILE, rule(fields))
                self.assertEqual(model.mode, mode)
                self.assertEqual(model.activate(("src/a.ts",))["activation"], "unknown")

    def test_missing_unclosed_and_oversized_headers_remain_explicit(self):
        for text, reason in (("Always use tabs.\n", "frontmatter_missing"),
                             ("---\nalwaysApply: true\n", "frontmatter_unclosed_or_over_limit"),
                             ("---\n" + "# line\n" * 130 + "---\n", "frontmatter_unclosed_or_over_limit")):
            with self.subTest(reason=reason):
                model = parse_cursor_rule(FILE, text)
                self.assertEqual((model.mode, model.reason), ("unknown", reason))

    def test_ambiguous_yaml_flags_and_patterns_never_become_inactive(self):
        headers = (
            'globs: src/**\nalwaysApply: "false"', 'globs: src/**',
            "alwaysApply: true\nalwaysApply: false", "alwaysApply: true\nunknownKey: value",
            "alwaysApply: true\ndescription: |\n  folded value", "alwaysApply: true\n<<: *defaults",
            'globs: ["src/**"]\nalwaysApply: false', "globs:\n  - src/**\nalwaysApply: false",
            'globs: "src/*.{ts,tsx}"\nalwaysApply: false', "globs: **/*.ts\nalwaysApply: false",
            "globs: true\nalwaysApply: false", "description: null\nalwaysApply: true",
            "globs: 0x10\nalwaysApply: false", "description: - value\nalwaysApply: true",
            r'description: "\ud800"' + "\nalwaysApply: true",
            'globs: "src/**,"\nalwaysApply: false',
            'globs: "' + ",".join("src/*" for _ in range(33)) + '"\nalwaysApply: false',
        )
        for header in headers:
            with self.subTest(header=header):
                model = parse_cursor_rule(FILE, rule(header))
                self.assertEqual(model.mode, "unknown")
                self.assertEqual(model.activate(("docs/a.ts",))["activation"], "unknown")

    def test_quoted_scalars_comments_bom_and_crlf_preserve_line_evidence(self):
        text = "\ufeff" + rule("# comment\ndescription: 'It''s a rule'\nglobs: 'src/**' # inline\nalwaysApply: false").replace("\n", "\r\n")
        model = parse_cursor_rule(FILE, text)
        self.assertEqual(model.activate(("src/a",))["activation"], "active")
        self.assertEqual(dict(model.metadata_lines)["globs"], 4)
        self.assertEqual(model.body_line, 7)

    def test_plain_md_and_unknown_extension_are_not_conflated(self):
        self.assertEqual(parse_cursor_rule(".cursor/rules/a.md", "anything").mode, "ignored")
        self.assertEqual(parse_cursor_rule(".cursor/rules/a.MDC", "anything").mode, "unknown")
        self.assertEqual(parse_cursor_rule("AGENTS.md", "anything").mode, "unknown")

    def test_activation_evidence_does_not_export_raw_metadata_values(self):
        model = parse_cursor_rule(FILE, rule('description: private-description\nglobs: private-pattern/**\nalwaysApply: false'))
        encoded = json.dumps(model.activate(("src/a",)))
        self.assertNotIn("private-description", encoded)
        self.assertNotIn("private-pattern", encoded)


if __name__ == "__main__":
    unittest.main()
