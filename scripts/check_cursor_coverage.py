"""Action adapter for strict coverage review. No network or instruction execution."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def run(base: Path, head: Path, prefixes: str, *, python: str = sys.executable) -> int:
    # Arguments remain separate values even for spaces, quotes or shell syntax.
    selected = [line.strip() for line in prefixes.splitlines() if line.strip()]
    if not selected or len(selected) > 64:
        raise ValueError("coverage-under requires 1 to 64 nonempty directory prefixes")
    directory = Path(tempfile.mkdtemp(prefix="acs-coverage-", dir=os.environ.get("RUNNER_TEMP")))
    if any(char in str(directory) for char in "\r\n"):
        raise ValueError("Coverage artifact directory is not suitable for GitHub outputs")
    markdown, output = directory / "review.md", directory / "review.json"
    args = [python, "-I", "-X", "utf8", "-m", "agent_config_score", "scope", "coverage", str(base), str(head),
            "--fail-on-lost-directives", "--fail-on-unknown", "--markdown", str(markdown), "--json"]
    args += ["--under=" + value for value in selected]
    result = subprocess.run(args, capture_output=True, encoding="utf-8", timeout=180)
    if result.returncode not in (0, 1):
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise ValueError("Cursor coverage could not complete; no successful coverage report is available")
    report = json.loads(result.stdout)
    if (report.get("status") != "completed" or report.get("analysis") != "cursor_single_file_coverage_comparison"
            or report.get("observed_agent_context") is not False or not markdown.is_file()):
        raise ValueError("Cursor coverage returned an incomplete report")
    summary, gate = report.get("summary"), report.get("review_gate")
    if not isinstance(summary, dict) or not isinstance(gate, dict):
        raise ValueError("Cursor coverage returned no structured gate result")
    counts = {"coverage-files": report["summary"]["files"],
              "coverage-lost-files": report["summary"]["files_with_losses"],
              "coverage-unknown-files": report["summary"]["files_with_unknown"]}
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("Cursor coverage returned invalid counts")
    if (counts["coverage-files"] == 0 or max(counts["coverage-lost-files"], counts["coverage-unknown-files"]) > counts["coverage-files"]
            or gate.get("fail_on_lost_directives") is not True or gate.get("fail_on_unknown") is not True
            or gate.get("failed") is not bool(counts["coverage-lost-files"] or counts["coverage-unknown-files"])
            or result.returncode != int(gate["failed"])):
        raise ValueError("Cursor coverage exit and configured review gate disagree")
    output.write_text(result.stdout, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as handle:
            handle.write(markdown.read_text(encoding="utf-8"))
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as handle:
            for key, value in {**counts, "coverage-json": output.as_posix(), "coverage-markdown": markdown.as_posix()}.items():
                handle.write(f"{key}={value}\n")
    return result.returncode


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--head", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        status = run(args.base, args.head, os.environ.get("ACS_COVERAGE_UNDER", ""))
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        status = 2
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            try:
                with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as handle:
                    handle.write("\n## Cursor coverage unavailable\n\nOperational failure (exit 2). Inspect the failed step log.\n")
            except OSError:
                print("error: could not append coverage failure summary", file=sys.stderr)
    if os.environ.get("GITHUB_OUTPUT"):
        try:
            with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as handle:
                handle.write(f"coverage-exit-code={status}\n")
        except OSError:
            print("error: could not export coverage status", file=sys.stderr)
            return 2
    return status


if __name__ == "__main__":
    raise SystemExit(main())
