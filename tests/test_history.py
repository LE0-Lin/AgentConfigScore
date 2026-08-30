from pathlib import Path

import pytest

from agent_config_score.history import append_snapshot, load_history, summarize_history


def test_append_and_load_history(tmp_path: Path):
    snapshot = {
        "commit": "abc123",
        "score": 95,
        "grade": "A",
    }

    append_snapshot(tmp_path, snapshot)

    history = load_history(tmp_path)

    assert len(history) == 1
    assert history[0]["commit"] == "abc123"
    assert history[0]["score"] == 95


def test_history_limit(tmp_path: Path):
    for index in range(5):
        append_snapshot(tmp_path, {"score": index}, limit=3)

    history = load_history(tmp_path)

    assert len(history) == 3
    assert history[0]["score"] == 2
    assert history[-1]["score"] == 4


def test_history_limit_must_be_positive(tmp_path: Path):
    with pytest.raises(ValueError, match="history limit must be >= 1"):
        append_snapshot(tmp_path, {"score": 100}, limit=0)


def test_invalid_history_returns_empty_list(tmp_path: Path):
    path = tmp_path / ".agentconfigscore" / "history" / "index.json"
    path.parent.mkdir(parents=True)
    path.write_text("not-json", encoding="utf-8")

    assert load_history(tmp_path) == []


def test_summarize_history_trend():
    summary = summarize_history([
        {"score": 91, "grade": "A"},
        {"score": 94, "grade": "A"},
        {"score": 97, "grade": "A"},
    ])

    assert summary == {
        "count": 3,
        "scored_count": 3,
        "first_score": 91,
        "latest_score": 97,
        "delta": 6,
        "trend": "up",
    }


def test_summarize_history_without_scores():
    summary = summarize_history([{"commit": "abc"}])

    assert summary["count"] == 1
    assert summary["scored_count"] == 0
    assert summary["delta"] is None
    assert summary["trend"] == "unknown"
