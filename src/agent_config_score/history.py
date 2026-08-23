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
    """Append a snapshot without overwriting previous history."""
    path = root / HISTORY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    history: list[dict[str, Any]] = []
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []

    history.append(snapshot)
    history = history[-limit:]
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_history(root: Path) -> list[dict[str, Any]]:
    path = root / HISTORY_FILE
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
