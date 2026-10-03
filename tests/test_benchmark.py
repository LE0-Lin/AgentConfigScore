import json
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "corpus.json"
RUNNER = ROOT / "scripts" / "run_real_world_benchmark.py"
SPEC = importlib.util.spec_from_file_location("real_world_benchmark", RUNNER)
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


class BenchmarkContractTests(unittest.TestCase):
    def test_clone_fetches_only_the_pinned_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            destination = Path(directory) / "snapshot"
            source.mkdir()

            def git(*args):
                return subprocess.run(
                    ["git", "-C", str(source), *args], check=True,
                    text=True, encoding="utf-8", capture_output=True,
                ).stdout.strip()

            git("init", "-q")
            (source / "AGENTS.md").write_text("Reviewed instructions.\n", encoding="utf-8")
            git("add", "AGENTS.md")
            git("-c", "user.name=Test", "-c", "user.email=test@example.com",
                "commit", "-qm", "reviewed")
            pinned = git("rev-parse", "HEAD")
            (source / "AGENTS.md").write_text("Later changed instructions.\n", encoding="utf-8")
            git("add", "AGENTS.md")
            git("-c", "user.name=Test", "-c", "user.email=test@example.com",
                "commit", "-qm", "later")

            BENCHMARK._clone({"url": str(source), "commit": pinned}, destination)
            self.assertEqual(
                (destination / "AGENTS.md").read_text(encoding="utf-8"),
                "Reviewed instructions.\n",
            )
            count = subprocess.run(
                ["git", "-C", str(destination), "rev-list", "--count", "HEAD"],
                check=True, text=True, capture_output=True,
            ).stdout.strip()
            self.assertEqual(count, "1")
            with self.assertRaises(FileExistsError):
                BENCHMARK._clone({"url": str(source), "commit": pinned}, destination)

    def test_stalled_git_command_has_an_actionable_timeout(self):
        with patch.object(BENCHMARK.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 180)):
            with self.assertRaisesRegex(RuntimeError, "timed out after 180 seconds"):
                BENCHMARK._run_git("fetch", "origin", "pinned-commit")

    def test_runner_help_is_available_offline(self):
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--work-dir", completed.stdout)
        self.assertIn("--repository", completed.stdout)

    def test_unknown_repository_selection_fails_before_network_access(self):
        with tempfile.TemporaryDirectory() as directory:
            corpus = Path(directory) / "corpus.json"
            corpus.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repositories": [
                            {
                                "name": "owner/known",
                                "url": "https://github.com/owner/known.git",
                                "commit": "0" * 40,
                                "expected": {},
                                "review_note": "fixture",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--corpus",
                    str(corpus),
                    "--repository",
                    "owner/missing",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("unknown repository selection: owner/missing", completed.stderr)

    def test_corpus_uses_unique_pinned_commits_and_reviewed_expectations(self):
        corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
        self.assertEqual(corpus["schema_version"], 1)
        repositories = corpus["repositories"]
        self.assertGreaterEqual(len(repositories), 3)
        self.assertEqual(len({row["name"] for row in repositories}), len(repositories))

        for repository in repositories:
            self.assertRegex(repository["commit"], re.compile(r"^[0-9a-f]{40}$"))
            self.assertTrue(repository["url"].startswith("https://github.com/"))
            self.assertTrue(repository["review_note"].strip())
            expected = repository["expected"]
            self.assertGreater(expected["files"], 0)
            self.assertIn(expected["grade"], {"A", "B", "C", "D", "F"})
            self.assertGreaterEqual(expected["score"], 0)
            self.assertLessEqual(expected["score"], 100)
            for finding in expected["findings"]:
                self.assertEqual(set(finding), {"code", "file", "line"})


if __name__ == "__main__":
    unittest.main()
