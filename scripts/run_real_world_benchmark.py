#!/usr/bin/env python3
"""Reproduce the pinned, read-only real-repository smoke benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

from agent_config_score import __version__
from agent_config_score.scanner import analyze


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "benchmarks" / "corpus.json"


def _run_git(*args: str, cwd: Path | None = None) -> None:
    command = ["git", *args]
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise RuntimeError(f"git command failed: {' '.join(command)}\n{detail}")


def _clone(repository: dict[str, Any], destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"benchmark destination already exists: {destination}")
    _run_git(
        "-c",
        "core.longpaths=true",
        "clone",
        "--filter=blob:none",
        "--no-checkout",
        repository["url"],
        str(destination),
    )
    _run_git("config", "core.longpaths", "true", cwd=destination)
    _run_git("checkout", "--detach", repository["commit"], cwd=destination)


def _fingerprints(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "code": finding["code"],
                "file": finding["file"],
                "line": finding.get("line"),
            }
            for finding in findings
        ),
        key=lambda row: (row["code"], row["file"], row["line"] or 0),
    )


def _scan(repository: dict[str, Any], destination: Path) -> dict[str, Any]:
    _clone(repository, destination)
    report = analyze(destination).to_dict()
    expected = repository["expected"]
    actual_findings = _fingerprints(report["findings"])
    expected_findings = _fingerprints(expected["findings"])
    matches = (
        len(report["files"]) == expected["files"]
        and report["score"] == expected["score"]
        and report["grade"] == expected["grade"]
        and actual_findings == expected_findings
    )
    return {
        "name": repository["name"],
        "url": repository["url"],
        "commit": repository["commit"],
        "files": len(report["files"]),
        "score": report["score"],
        "grade": report["grade"],
        "estimated_tokens": report["estimated_tokens"],
        "findings": actual_findings,
        "matches_reviewed_expectation": matches,
        "review_note": repository["review_note"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.work_dir is None:
        temporary = tempfile.TemporaryDirectory(prefix="agentconfigscore-benchmark-")
        work_dir = Path(temporary.name)
    else:
        work_dir = args.work_dir.resolve()
        work_dir.mkdir(parents=True, exist_ok=True)

    try:
        repositories = [
            _scan(repository, work_dir / repository["name"].replace("/", "--"))
            for repository in corpus["repositories"]
        ]
    finally:
        if temporary is not None:
            temporary.cleanup()

    result = {
        "schema_version": 1,
        "agent_config_score_version": __version__,
        "corpus": str(args.corpus),
        "all_matched": all(row["matches_reviewed_expectation"] for row in repositories),
        "repositories": repositories,
    }
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}")
    return 0 if result["all_matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
