import json
import importlib.util
import contextlib
import io
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "corpus.json"
RUNNER = ROOT / "scripts" / "run_real_world_benchmark.py"
SPEC = importlib.util.spec_from_file_location("real_world_benchmark", RUNNER)
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


class BenchmarkContractTests(unittest.TestCase):
    def repository(self, expected=None):
        return {"name": "owner/repo", "url": "https://github.com/owner/repo.git",
                "commit": "0" * 40, "review_note": "Synthetic fixture",
                "expected": expected if expected is not None else {
                    "files": 1, "score": 100, "grade": "A", "findings": []}}

    def report(self):
        return SimpleNamespace(to_dict=lambda: {
            "files": ["AGENTS.md"], "score": 100, "grade": "A", "estimated_tokens": 8, "findings": []})

    def test_acquisition_failure_is_never_a_prediction_or_expected_success(self):
        with patch.object(BENCHMARK, "_clone", side_effect=RuntimeError("private transport detail")), \
                patch.object(BENCHMARK, "analyze") as analyze:
            result = BENCHMARK._scan(self.repository(), Path("unused"))
        analyze.assert_not_called()
        self.assertEqual(result["status"], "acquisition_error")
        self.assertFalse(result["matches_reviewed_expectation"])
        for key in ("files", "score", "grade", "findings", "estimated_tokens"):
            self.assertIsNone(result[key])
        self.assertNotIn("private transport detail", json.dumps(result))

    def test_operational_failure_is_unscored_and_requires_exact_explicit_expectation(self):
        expected = {"status": "scan_error", "error_type": "FileNotFoundError", "error_errno": 2}
        for declared, error, matches in (
            (None, FileNotFoundError(2, "private path"), False),
            (expected, FileNotFoundError(2, "private path"), True),
            (expected, PermissionError(13, "private path"), False),
        ):
            with self.subTest(declared=declared, error=type(error).__name__):
                with patch.object(BENCHMARK, "_clone"), patch.object(BENCHMARK, "analyze", side_effect=error):
                    result = BENCHMARK._scan(self.repository(declared), Path("unused"))
                self.assertEqual(result["status"], "scan_error")
                self.assertEqual(result["matches_reviewed_expectation"], matches)
                self.assertIsNone(result["score"])
                self.assertIsNone(result["findings"])
                self.assertNotIn("private path", json.dumps(result))

    def test_success_when_rejection_was_expected_remains_a_mismatch(self):
        expected = {"status": "scan_error", "error_type": "FileNotFoundError", "error_errno": 2}
        with patch.object(BENCHMARK, "_clone"), patch.object(BENCHMARK, "analyze", return_value=self.report()):
            result = BENCHMARK._scan(self.repository(expected), Path("unused"))
        self.assertEqual(result["status"], "scanned")
        self.assertFalse(result["matches_reviewed_expectation"])

    def test_expected_rejection_is_not_all_scans_completed(self):
        row = {"status": "scan_error", "matches_reviewed_expectation": True}
        result = BENCHMARK._result([row], 1, Path("corpus.json"), {})
        self.assertTrue(result["all_matched"])
        self.assertTrue(result["all_completed"])
        self.assertFalse(result["all_scans_completed"])
        self.assertEqual(result["summary"]["scanned"], 0)
        self.assertEqual(result["summary"]["matched_expected_scan_errors"], 1)

    def test_empty_or_acquisition_success_expectations_are_rejected(self):
        for repositories in ([], [self.repository({"status": "acquisition_error"})],
                             [self.repository({"status": "scan_error", "error_type": "OSError", "error_errno": True})]):
            with self.assertRaises(ValueError):
                BENCHMARK._validate_expectations(repositories)

    def test_failed_middle_repository_preserves_earlier_and_later_results(self):
        with tempfile.TemporaryDirectory() as directory:
            corpus, output = Path(directory) / "corpus.json", Path(directory) / "result.json"
            repositories = [{**self.repository(), "name": f"owner/repo-{i}"} for i in range(3)]
            corpus.write_text(json.dumps({"repositories": repositories}), encoding="utf-8")
            snapshots = []
            writer = BENCHMARK._write_result

            def retain(path, result):
                snapshots.append((result["summary"]["recorded"], result["all_completed"]))
                writer(path, result)

            with patch.object(sys, "argv", [str(RUNNER), "--corpus", str(corpus), "--output", str(output)]), \
                    patch.object(BENCHMARK, "_clone", side_effect=[None, RuntimeError("failure"), None]), \
                    patch.object(BENCHMARK, "analyze", return_value=self.report()), \
                    patch.object(BENCHMARK, "_write_result", side_effect=retain), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(BENCHMARK.main(), 1)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual([row["status"] for row in result["repositories"]],
                             ["scanned", "acquisition_error", "scanned"])
            self.assertEqual(snapshots[:3], [(1, False), (2, False), (3, True)])
            self.assertFalse(result["all_matched"])
            self.assertFalse(result["all_scans_completed"])
            self.assertEqual(result["summary"]["scanned"], 2)
            self.assertIn("source_fingerprint", result["tool"])

    def test_unexpected_programming_error_leaves_explicitly_partial_report(self):
        with tempfile.TemporaryDirectory() as directory:
            corpus, output = Path(directory) / "corpus.json", Path(directory) / "result.json"
            repositories = [{**self.repository(), "name": f"owner/repo-{i}"} for i in range(2)]
            corpus.write_text(json.dumps({"repositories": repositories}), encoding="utf-8")
            with patch.object(sys, "argv", [str(RUNNER), "--corpus", str(corpus), "--output", str(output)]), \
                    patch.object(BENCHMARK, "_clone"), \
                    patch.object(BENCHMARK, "analyze", side_effect=[self.report(), ValueError("bug")]), \
                    self.assertRaisesRegex(ValueError, "bug"):
                BENCHMARK.main()
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["summary"]["recorded"], 1)
            self.assertFalse(result["all_completed"])
            self.assertFalse(result["all_matched"])

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
            if expected.get("status") == "scan_error":
                self.assertEqual(set(expected), {"status", "error_type", "error_errno"})
                self.assertEqual(expected["error_type"], "FileNotFoundError")
                self.assertEqual(expected["error_errno"], 2)
                continue
            self.assertGreater(expected["files"], 0)
            self.assertIn(expected["grade"], {"A", "B", "C", "D", "F"})
            self.assertGreaterEqual(expected["score"], 0)
            self.assertLessEqual(expected["score"], 100)
            for finding in expected["findings"]:
                self.assertEqual(set(finding), {"code", "file", "line"})


if __name__ == "__main__":
    unittest.main()
