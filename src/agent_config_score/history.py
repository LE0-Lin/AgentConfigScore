from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
import stat
import tempfile
from typing import Any

HISTORY_DIR = Path(".agentconfigscore") / "history"
HISTORY_FILE = HISTORY_DIR / "index.json"


class HistoryError(ValueError):
    """Local history could not be read or safely updated; do not reset it."""


def _history_path(root: Path) -> tuple[Path, os.stat_result | None]:
    path = root / HISTORY_FILE
    current = root
    try:
        for part in HISTORY_FILE.parts:
            current = current / part
            try:
                info = current.lstat()
            except FileNotFoundError:
                return path, None
            reparse = (getattr(info, "st_file_attributes", 0)
                       & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
            if stat.S_ISLNK(info.st_mode) or reparse:
                raise HistoryError("Local history uses a linked or reparse path; back up and migrate it manually")
            if current == path:
                if not stat.S_ISREG(info.st_mode):
                    raise HistoryError("Local history index must be a regular JSON file")
                return path, info
            if not stat.S_ISDIR(info.st_mode):
                raise HistoryError("Local history parent must be a directory")
    except OSError as exc:
        raise HistoryError("Could not inspect local history; check filesystem access") from exc
    raise HistoryError("Could not locate local history")  # HISTORY_FILE is always nonempty.


def _unique_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    data = {}
    for key, value in pairs:
        if key in data:
            raise HistoryError("Invalid local history: duplicate JSON member names; back up and repair the index")
        data[key] = value
    return data


def _reject_constant(_value: str) -> None:
    raise HistoryError("Invalid local history: non-finite JSON numbers are not supported")


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        _reject_constant(value)
    return result


def _validate_history(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
        raise HistoryError("Invalid local history: expected an array of snapshot objects; back up and repair the index")
    for item in data:
        score = item.get("score")
        if score is not None and (
            isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100
        ):
            raise HistoryError("Invalid local history: score must be a finite number from 0 to 100 or null")
    return data


def _decode_history(text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text, object_pairs_hook=_unique_members,
                          parse_constant=_reject_constant, parse_float=_finite_float)
    except HistoryError:
        raise
    except (ValueError, RecursionError) as exc:
        raise HistoryError("Invalid local history JSON; back up and repair .agentconfigscore/history/index.json") from exc
    return _validate_history(data)


def create_snapshot(report: Any, *, commit: str | None = None) -> dict[str, Any]:
    """Create a stable read-only score history snapshot."""
    findings = getattr(report, "findings", [])
    tool = getattr(report, "tool", None)
    return {
        "tool": tool.to_dict() if tool is not None else None,
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
    """Validate the entire store, then replace it with a complete bounded list.

    No writer locking or hostile-filesystem transaction is provided. Callers
    must serialize updates; retention is intentional, not corruption recovery.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("history limit must be >= 1")
    _validate_history([snapshot])
    history = load_history(root)
    history.append(snapshot)
    history = history[-limit:]
    try:
        text = json.dumps(history, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        _decode_history(text)  # Also detect duplicate names after JSON key conversion.
        payload = text.encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise HistoryError("Invalid local history snapshot; no history was written") from exc

    path, previous = _history_path(root)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _history_path(root)
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=".index-", suffix=".tmp", delete=False) as target:
            temporary = Path(target.name)
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        if previous is not None:
            os.chmod(temporary, stat.S_IMODE(previous.st_mode))
        _history_path(root)
        os.replace(temporary, path)
    except OSError as exc:
        raise HistoryError("Could not replace local history; existing index was not intentionally truncated; inspect before retrying") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                # Cleanup failure must not conceal the original failure. The
                # uniquely named temporary file may need manual removal.
                pass
    return path


def load_history(root: Path) -> list[dict[str, Any]]:
    """Only absent history is empty; damaged/unreadable history is an error."""
    path, info = _history_path(root)
    if info is None:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise HistoryError("Could not read local history as UTF-8; back up the index and check filesystem access") from exc
    return _decode_history(text)


def summarize_history(history: list[dict[str, Any]]) -> dict[str, Any]:
    """Return stable trend metadata for a sequence of score snapshots."""
    _validate_history(history)
    scored = [item for item in history if item.get("score") is not None]
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
