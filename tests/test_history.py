import tempfile
import unittest
from pathlib import Path

from agent_config_score.history import append_snapshot, load_history, summarize_history


class HistoryTests(unittest.TestCase):
    def test_append_and_load_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = {
                "commit": "abc123",
                "score": 95,
                "grade": "A",
            }

            append_snapshot(root, snapshot)

            history = load_history(root)

            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["commit"], "abc123")
            self.assertEqual(history[0]["score"], 95)

    def test_history_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(5):
                append_snapshot(root, {"score": index}, limit=3)

            history = load_history(root)

            self.assertEqual(len(history), 3)
            self.assertEqual(history[0]["score"], 2)
            self.assertEqual(history[-1]["score"], 4)

    def test_history_limit_must_be_positive(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "history limit must be >= 1"):
                append_snapshot(Path(directory), {"score": 100}, limit=0)

    def test_invalid_history_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".agentconfigscore" / "history" / "index.json"
            path.parent.mkdir(parents=True)
            path.write_text("not-json", encoding="utf-8")

            self.assertEqual(load_history(root), [])

    def test_summarize_history_trend(self):
        summary = summarize_history([
            {"score": 91, "grade": "A"},
            {"score": 94, "grade": "A"},
            {"score": 97, "grade": "A"},
        ])

        self.assertEqual(summary, {
            "count": 3,
            "scored_count": 3,
            "first_score": 91,
            "latest_score": 97,
            "delta": 6,
            "trend": "up",
        })

    def test_summarize_history_without_scores(self):
        summary = summarize_history([{"commit": "abc"}])

        self.assertEqual(summary["count"], 1)
        self.assertEqual(summary["scored_count"], 0)
        self.assertIsNone(summary["delta"])
        self.assertEqual(summary["trend"], "unknown")


if __name__ == "__main__":
    unittest.main()
