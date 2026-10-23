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
from agent_config_score.provenance import capture_tool_identity
from agent_config_score.scanner import analyze


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "benchmarks" / "corpus.json"


def _run_git(*args: str, cwd: Path | None = None) -> None:
    command = ["git", *args]
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=180,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"git command timed out after 180 seconds: {' '.join(command)}"
        ) from exc
    if completed.returncode:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise RuntimeError(f"git command failed: {' '.join(command)}\n{detail}")


def _clone(repository: dict[str, Any], destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"benchmark destination already exists: {destination}")
    _run_git(
        "-c",
        "core.longpaths=true",
        "init",
        "--quiet",
        str(destination),
    )
    _run_git("config", "core.longpaths", "true", cwd=destination)
    _run_git("remote", "add", "origin", repository["url"], cwd=destination)
    # Fetch only the reviewed snapshot. A history clone with lazy blobs can
    # require extra remote requests for every checkout and grow over time.
    _run_git("fetch", "--no-tags", "--depth=1", "origin", repository["commit"], cwd=destination)
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
    identity = {key: repository[key] for key in ("name", "url", "commit", "review_note")}
    empty = {"files": None, "score": None, "grade": None, "estimated_tokens": None, "findings": None}
    try:
        _clone(repository, destination)
    except (OSError, RuntimeError) as exc:
        # Acquisition is never a prediction or an expected clean result.
        return {**identity, **empty, "status": "acquisition_error", "error_type": type(exc).__name__,
                "error_errno": getattr(exc, "errno", None), "matches_reviewed_expectation": False}
    expected = repository["expected"]
    try:
        report = analyze(destination).to_dict()
    except OSError as exc:
        matches = (expected.get("status") == "scan_error"
                   and type(exc).__name__ == expected["error_type"]
                   and exc.errno == expected["error_errno"])
        return {**identity, **empty, "status": "scan_error", "error_type": type(exc).__name__,
                "error_errno": exc.errno, "matches_reviewed_expectation": matches}
    actual_findings = _fingerprints(report["findings"])
    matches = (
        expected.get("status", "scanned") == "scanned"
        and len(report["files"]) == expected["files"]
        and report["score"] == expected["score"] and report["grade"] == expected["grade"]
        and actual_findings == _fingerprints(expected["findings"])
    )
    return {
        "name": repository["name"],
        "url": repository["url"],
        "commit": repository["commit"],
        "status": "scanned",
        "files": len(report["files"]),
        "score": report["score"],
        "grade": report["grade"],
        "estimated_tokens": report["estimated_tokens"],
        "findings": actual_findings,
        "matches_reviewed_expectation": matches,
        "review_note": repository["review_note"],
    }


def _validate_expectations(repositories: list[dict[str, Any]]) -> None:
    if not repositories:
        raise ValueError("benchmark requires at least one repository")
    for repository in repositories:
        expected = repository["expected"]
        status = expected.get("status", "scanned")
        if status == "scan_error":
            if (set(expected) != {"status", "error_type", "error_errno"}
                    or expected["error_type"] not in {
                        "OSError", "FileNotFoundError", "PermissionError", "NotADirectoryError", "IsADirectoryError"}
                    or type(expected["error_errno"]) is not int or expected["error_errno"] <= 0):
                raise ValueError("invalid explicit scan-error expectation")
        elif status != "scanned" or not all(key in expected for key in ("files", "score", "grade", "findings")):
            raise ValueError("invalid scan expectation; acquisition errors cannot be expected successes")


def _result(repositories: list[dict[str, Any]], requested: int, corpus: Path, tool: dict) -> dict:
    complete = len(repositories) == requested
    return {
        "schema_version": 1, "agent_config_score_version": __version__, "tool": tool,
        "corpus": str(corpus), "all_completed": complete,
        "all_scans_completed": complete and all(row["status"] == "scanned" for row in repositories),
        "all_matched": complete and all(row["matches_reviewed_expectation"] for row in repositories),
        "summary": {
            "requested": requested, "recorded": len(repositories),
            "scanned": sum(row["status"] == "scanned" for row in repositories),
            "acquisition_errors": sum(row["status"] == "acquisition_error" for row in repositories),
            "scan_errors": sum(row["status"] == "scan_error" for row in repositories),
            "matched_expected_scan_errors": sum(row["status"] == "scan_error" and row["matches_reviewed_expectation"]
                                                for row in repositories),
        },
        "repositories": repositories,
    }


def _write_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--repository",
        action="append",
        metavar="OWNER/REPO",
        help="Run only a named corpus repository; repeat to select multiple repositories",
    )
    return parser


def _select_repositories(
    repositories: list[dict[str, Any]],
    selected_names: list[str] | None,
) -> list[dict[str, Any]]:
    if not selected_names:
        return repositories
    requested = set(selected_names)
    known = {repository["name"] for repository in repositories}
    unknown = sorted(requested - known)
    if unknown:
        raise ValueError(
            "unknown repository selection: "
            + ", ".join(unknown)
            + "; choose from: "
            + ", ".join(sorted(known))
        )
    return [repository for repository in repositories if repository["name"] in requested]


def main() -> int:
    args = _parser().parse_args()
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    try:
        selected_repositories = _select_repositories(
            corpus["repositories"], args.repository
        )
        _validate_expectations(selected_repositories)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if args.work_dir is None:
        temporary = tempfile.TemporaryDirectory(prefix="agentconfigscore-benchmark-")
        work_dir = Path(temporary.name)
    else:
        work_dir = args.work_dir.resolve()
        work_dir.mkdir(parents=True, exist_ok=True)

    repositories = []
    tool = capture_tool_identity().to_dict()
    try:
        for repository in selected_repositories:
            repositories.append(_scan(repository, work_dir / repository["name"].replace("/", "--")))
            result = _result(repositories, len(selected_repositories), args.corpus, tool)
            if args.output is not None:
                _write_result(args.output, result)
    finally:
        if temporary is not None:
            temporary.cleanup()

    result = _result(repositories, len(selected_repositories), args.corpus, tool)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        _write_result(args.output, result)
        print(f"wrote {args.output}")
    return 0 if result["all_matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
