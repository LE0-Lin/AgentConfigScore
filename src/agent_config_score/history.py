from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HISTORY_DIR = Path(".agentconfigscore") / "history"
HISTORY_FILE = HISTORY_DIR / "index.json"


def create_snapshot(report: Any, *, commit: str | None = None) -> dict[str, Any]:
    """Create a stable read-only score history snapshot."""
    findings = getattr(report, "findings", [])
    return {
        "commit": commit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score": report.score,
        "grade": report.grade,
        "files": len(report.files),
        "findings": {
            "total": len(findings),
        },
    }


def append_snapshot(root: Path, snapshot: dict[str, Any], *, limit: int = 100) -> Path:
    """Append a snapshot while retaining only the newest entries."""
    if limit < 1:
        raise ValueError("history limit must be >= 1")

    path = root / HISTORY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    history = load_history(root)
    history.append(snapshot)
    history = history[-limit:]
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_history(root: Path) -> list[dict[str, Any]]:
    """Load local score history, returning an empty list for missing or invalid files."""
    path = root / HISTORY_FILE
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def summarize_history(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Return stable trend metadata for a sequence of score snapshots."""
    scored = [item for item in history if isinstance(item.get("score"), (int, float))]
    if not scored:
        return {
            "count": len(history),
            "scored_count": 0,
            "first_score": None,
            "latest_score": None,
            "delta": None,
            "trend": "unknown",
        }

    first = scored[0]["score"]
    latest = scored[-1]["score"]
    delta = latest - first
    trend = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return {
        "count": len(history),
        "scored_count": len(scored),
        "first_score": first,
        "latest_score": latest,
        "delta": delta,
        "trend": trend,
    }
