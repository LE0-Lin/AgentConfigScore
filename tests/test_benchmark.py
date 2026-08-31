import json
from pathlib import Path
import re
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "corpus.json"
RUNNER = ROOT / "scripts" / "run_real_world_benchmark.py"


class BenchmarkContractTests(unittest.TestCase):
    def test_runner_help_is_available_offline(self):
        completed = subprocess.run(
            [sys.executable, str(RUNNER), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--work-dir", completed.stdout)

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
