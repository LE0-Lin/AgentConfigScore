import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_config_score.scanner import _candidate_exists, _repository_path_index, analyze, discover


FORMATS = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules",
           ".github/copilot-instructions.md", ".cursor/rules/review.mdc")


class PathReferenceTests(unittest.TestCase):
    def findings(self, text, filename="AGENTS.md", existing=()):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in existing:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("source\n", encoding="utf-8")
            source = root / filename
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(text, encoding="utf-8")
            return analyze(root).findings

    def dead_lines(self, text, **kwargs):
        return [f.line for f in self.findings(text, **kwargs) if f.code == "dead-path"]

    def test_repository_roles_are_not_local_paths_across_formats(self):
        text = (
            "The branch is part of the `acme/tool.js` repository.\n"
            "Resolve the `acme/tool.py` remote itself, then fetch it.\n"
            "Fork PRs have a merge target is `acme/tool.ts`.\n"
            "Commits are re-pushed to a branch in `acme/tool.rs`.\n"
            "CI trusts branches inside `acme/tool.json`.\n"
            "The GitHub repository is a fork of `acme/tool.js` and not `acme/tool.js` itself.\n"
        )
        for filename in FORMATS:
            with self.subTest(filename=filename):
                self.assertEqual(self.dead_lines(text, filename=filename), [])

    def test_repository_words_do_not_hide_local_files(self):
        text = (
            "The GitHub repository uses `src/missing.js`.\n"
            "Read `src/config.json` repository file before proceeding.\n"
            "Use a branch in `src/missing.ts`.\n"
            "The `acme/tool.js` repository. Read `src/missing.py`.\n"
            "Resolve the `acme/tool.js` remote itself.\n"
            "Read `src/missing.rs` first.\n"
            "A fork of `acme/tool.js` and not `src/local.js` itself.\n"
            "A fork of `acme/tool.js`; read `src/local.js`.\n"
            "The `acme/tool.js`\nrepository.\n"
        )
        self.assertEqual(self.dead_lines(text), [1, 2, 3, 4, 6, 7, 8, 9])

    def test_closed_immediate_existence_conditions_across_formats(self):
        text = (
            "Read `docs/guide.md` (if exists).\n"
            "Read `docs/guide.md` (if it exists).\n"
            "Read docs/guide.md (IF EXISTS - closest to target file).\n"
            "Read `docs/guide.md` (if exists: closest to target file).\n"
            "Read `docs/guide.md` (if exists), then `src/required.py`.\n"
            "Read `src/another.py`, then `docs/guide.md` (if exists).\n"
        )
        for filename in FORMATS:
            with self.subTest(filename=filename):
                self.assertEqual(self.dead_lines(text, filename=filename), [5, 6])

    def test_optional_words_do_not_hide_required_paths(self):
        text = (
            "Optional workflow: read `src/missing.py`.\n"
            "Read `src/missing.py` (if needed).\n"
            "Read `src/missing.py` (if exists\n"
            "Read `src/missing.py`\n(if exists).\n"
            "Read `src/missing.py` first (if exists).\n"
            "Read `src/missing.py` (if exists and is writable).\n"
            "Read `src/missing.py` (if exists: (nested)).\n"
        )
        self.assertEqual(self.dead_lines(text), [1, 2, 3, 4, 6, 7, 8])

    def test_actual_markdown_links_still_require_targets(self):
        text = (
            "[Guide](docs/missing.md) (if exists).\n"
            "[Remote](acme/tool.js) repository.\n"
        )
        self.assertEqual(self.dead_lines(text), [1, 2])

    def test_path_context_never_exempts_dangerous_commands(self):
        text = "Read `docs/guide.md` (if exists), then run `rm -rf cache`.\n"
        findings = self.findings(text)
        self.assertNotIn("dead-path", [f.code for f in findings])
        self.assertIn("rm-rf", [f.code for f in findings])

    def test_package_relative_source_in_build_named_trees_is_found(self):
        for name in ("build", "dist", "target", ".next"):
            with self.subTest(name=name):
                self.assertEqual(self.dead_lines(
                    f"Build entry: `src/{name}/index.ts`.\n",
                    existing=(f"packages/client/src/{name}/index.ts",)), [])
                self.assertEqual(self.dead_lines(f"Build entry: `src/{name}/missing.ts`.\n"), [1])

    def test_path_index_changes_do_not_expand_instruction_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("Root instructions.\n", encoding="utf-8")
            for name in ("build", "dist", "target", ".next", "node_modules", ".git", "vendor"):
                path = root / "packages" / "client" / name
                path.mkdir(parents=True)
                (path / "AGENTS.md").write_text("Do not discover this.\n", encoding="utf-8")
                (path / "index.ts").write_text("source\n", encoding="utf-8")
            self.assertEqual(discover(root), [root / "AGENTS.md"])
            index = _repository_path_index(root)
            for name in ("build", "dist", "target", ".next"):
                self.assertIn(f"packages/client/{name}/index.ts", index)
            for name in ("node_modules", ".git", "vendor"):
                self.assertNotIn(f"packages/client/{name}/index.ts", index)

    def test_dependency_tree_cannot_satisfy_package_relative_reference(self):
        self.assertEqual(self.dead_lines("Read `src/dependency.py`.\n",
                         existing=("node_modules/client/src/dependency.py",)), [1])

    def test_explicit_relative_path_cannot_use_unrelated_suffix_match(self):
        self.assertEqual(self.dead_lines("Read `./src/entry.py`.\n",
                         existing=("packages/client/src/entry.py",)), [1])
        self.assertEqual(self.dead_lines("Read `./src/entry.py`.\n",
                         existing=("src/entry.py",)), [])

    def test_backslash_relative_reference_uses_the_same_anchor(self):
        filename = "packages/client/AGENTS.md"
        self.assertEqual(self.dead_lines(r"Read `.\src\entry.py`." + "\n", filename=filename,
                         existing=("packages/other/src/entry.py",)), [1])
        self.assertEqual(self.dead_lines(r"Read `..\docs\guide.md`." + "\n", filename=filename,
                         existing=("packages/docs/guide.md",)), [])

    def test_explicit_relative_path_accepts_existing_root_or_instruction_scope(self):
        for filename in ("packages/client/AGENTS.md", "packages/client/CLAUDE.md",
                         ".github/copilot-instructions.md", ".cursor/rules/review.mdc"):
            with self.subTest(filename=filename):
                self.assertEqual(self.dead_lines("Read `./src/entry.py`.\n", filename=filename,
                                 existing=("src/entry.py",)), [])
                local = str(Path(filename).parent / "src" / "entry.py")
                self.assertEqual(self.dead_lines("Read `./src/entry.py`.\n", filename=filename,
                                 existing=(local,)), [])
                self.assertEqual(self.dead_lines("Read `./src/entry.py`.\n", filename=filename,
                                 existing=("packages/other/src/entry.py",)), [1])

    def test_parent_relative_path_cannot_choose_an_unrelated_suffix(self):
        filename = "packages/client/instructions/AGENTS.md"
        self.assertEqual(self.dead_lines("Read `../docs/guide.md`.\n", filename=filename,
                         existing=("packages/other/docs/guide.md",)), [1])
        self.assertEqual(self.dead_lines("Read `../docs/guide.md`.\n", filename=filename,
                         existing=("packages/client/docs/guide.md",)), [])
        self.assertEqual(self.dead_lines("Read `../docs/guide.md`.\n", filename=filename,
                         existing=("docs/guide.md",)), [])

    def test_hidden_directory_dot_is_preserved_in_suffix_lookup(self):
        self.assertEqual(self.dead_lines("Read `.github/guide.md`.\n",
                         existing=("packages/client/github/guide.md",)), [1])
        self.assertEqual(self.dead_lines("Read `.github/guide.md`.\n",
                         existing=("packages/client/.github/guide.md",)), [])

    def test_outside_reference_does_not_become_an_in_repo_suffix_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.object(Path, "exists", side_effect=AssertionError("outside path probed")):
                self.assertIsNone(_candidate_exists(root, root / "AGENTS.md", "../src/entry.py",
                                                    {"src/entry.py"}))

    def test_path_index_read_failure_is_not_a_partial_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            blocked = root / "src"
            blocked.mkdir()
            original = os.scandir

            def inaccessible(path):
                if Path(path) == blocked:
                    raise PermissionError(13, "sensitive-error-detail", str(blocked))
                return original(path)

            with patch("agent_config_score.scanner.os.scandir", side_effect=inaccessible):
                with self.assertRaises(OSError) as caught:
                    _repository_path_index(root)
            self.assertNotIn("sensitive-error-detail", str(caught.exception))

    def test_unreadable_dependency_tree_remains_pruned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "AGENTS.md").write_text("Run tests.\n", encoding="utf-8")
            blocked = root / "node_modules"
            blocked.mkdir()
            original = os.scandir

            def inaccessible(path):
                if Path(path) == blocked:
                    raise PermissionError(13, "excluded dependency tree")
                return original(path)

            with patch("agent_config_score.scanner.os.scandir", side_effect=inaccessible):
                index = _repository_path_index(root)
            self.assertIn("AGENTS.md", index)
            self.assertNotIn("node_modules", index)

    def test_dependency_tree_is_pruned_before_descent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            excluded = root / "node_modules" / "nested"
            excluded.mkdir(parents=True)
            (excluded / "entry.py").write_text("source\n", encoding="utf-8")
            visited = []
            original = os.scandir

            def traced(path):
                visited.append(Path(path))
                return original(path)

            with patch("agent_config_score.scanner.os.scandir", side_effect=traced):
                _repository_path_index(root)
            self.assertIn(root, visited)
            self.assertNotIn(root / "node_modules", visited)
            self.assertNotIn(excluded, visited)

    def test_index_does_not_follow_directory_links_or_external_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "repo"
            root.mkdir()
            outside = workspace / "outside"
            outside.mkdir()
            (outside / "entry.py").write_text("outside\n", encoding="utf-8")
            inside = root / "real"
            inside.mkdir()
            (inside / "entry.py").write_text("inside\n", encoding="utf-8")
            try:
                os.symlink(outside, root / "external", target_is_directory=True)
                os.symlink(inside, root / "alias", target_is_directory=True)
                os.symlink(outside / "entry.py", root / "external.py")
                os.symlink(root / "absent.py", root / "broken.py")
            except OSError:
                self.skipTest("symlink creation is unavailable")
            index = _repository_path_index(root)
            self.assertIn("real/entry.py", index)
            self.assertIn("alias", index)
            for name in ("external", "external/entry.py", "alias/entry.py", "external.py", "broken.py"):
                self.assertNotIn(name, index)


if __name__ == "__main__":
    unittest.main()
