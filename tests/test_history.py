from pathlib import Path

from agent_config_score.history import append_snapshot, load_history


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
