from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .regression import compare, markdown_report
from .sarif import sarif_report
from .scanner import analyze, badge_svg, html_report

RESET = "\033[0m"
BOLD = "\033[1m"
COLORS = {"error": "\033[31m", "warning": "\033[33m", "info": "\033[36m"}
GRADE_COLORS = {"A": "\033[32m", "B": "\033[32m", "C": "\033[33m", "D": "\033[33m", "F": "\033[31m"}


def _supports_color() -> bool:
    return sys.stdout.isatty()


def _c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}" if _supports_color() else text


def print_report(report) -> None:
    grade = _c(report.grade, GRADE_COLORS[report.grade])
    print(f"\n{BOLD if _supports_color() else ''}AgentConfigScore{RESET if _supports_color() else ''}  {grade}  {report.score}/100")
    print(f"Files: {len(report.files)}   Estimated tokens: {report.estimated_tokens:,}   Duplication: {report.duplicate_ratio:.0%}\n")
    if not report.findings:
        print(_c("✓ No findings", "\033[32m"))
        return
    for f in report.findings:
        icon = {"error": "✖", "warning": "!", "info": "i"}.get(f.severity, "-")
        loc = f.file + (f":{f.line}" if f.line else "")
        prefix = _c(f"{icon} {f.severity.upper():7}", COLORS.get(f.severity, ""))
        print(f"{prefix} {f.code:20} {f.message}")
        print(f"           {loc}")


def print_regression(report) -> None:
    sign = "+" if report.delta > 0 else ""
    print(
        f"\n{BOLD if _supports_color() else ''}AgentConfigScore regression{RESET if _supports_color() else ''}  "
        f"{report.base.grade} {report.base.score} → {report.head.grade} {report.head.score} ({sign}{report.delta})"
    )
    print(f"New findings: {len(report.new_findings)}   Resolved: {len(report.resolved_findings)}\n")
    for finding in report.new_findings:
        location = finding.file + (f":{finding.line}" if finding.line else "")
        prefix = _c(f"+ {finding.severity.upper():7}", COLORS.get(finding.severity, ""))
        print(f"{prefix} {finding.code:20} {finding.message}")
        print(f"           {location}")
    for finding in report.resolved_findings:
        location = finding.file + (f":{finding.line}" if finding.line else "")
        print(f"- RESOLVED {finding.code:20} {finding.message}")
        print(f"           {location}")
    if not report.new_findings and not report.resolved_findings:
        print("✓ No agent-config changes detected")


def build_scan_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent-config-score", description="Score and audit coding-agent instruction files.")
    p.add_argument("path", nargs="?", default=".", help="Repository path (default: current directory)")
    p.add_argument("--json", action="store_true", help="Print JSON instead of text")
    p.add_argument("--html", metavar="FILE", help="Write a self-contained HTML report")
    p.add_argument("--badge", metavar="FILE", help="Write an SVG score badge")
    p.add_argument("--sarif", metavar="FILE", help="Write a SARIF 2.1.0 report for GitHub code scanning")
    p.add_argument("--fail-under", type=int, default=None, metavar="N", help="Exit non-zero when score is below N")
    return p


def build_compare_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-config-score compare",
        description="Compare two repository trees and fail only when agent configuration regresses.",
    )
    p.add_argument("base", help="Baseline repository directory")
    p.add_argument("head", help="Candidate repository directory")
    p.add_argument("--json", action="store_true", help="Print JSON instead of text")
    p.add_argument("--markdown", metavar="FILE", help="Write a Markdown regression summary")
    p.add_argument("--max-drop", type=int, default=0, metavar="N", help="Allowed score drop before failing (default: 0)")
    p.add_argument("--fail-on-new-errors", action="store_true", help="Fail when the candidate introduces any new error finding")
    return p


def _existing_dir(value: str) -> Path | None:
    path = Path(value)
    return path if path.exists() and path.is_dir() else None


def _main_compare(argv: list[str]) -> int:
    args = build_compare_parser().parse_args(argv)
    base = _existing_dir(args.base)
    head = _existing_dir(args.head)
    if base is None:
        print(f"error: not a directory: {args.base}", file=sys.stderr)
        return 2
    if head is None:
        print(f"error: not a directory: {args.head}", file=sys.stderr)
        return 2
    if args.max_drop < 0:
        print("error: --max-drop must be >= 0", file=sys.stderr)
        return 2

    report = compare(base, head)
    if args.markdown:
        out = Path(args.markdown)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown_report(report), encoding="utf-8")

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print_regression(report)
        if args.markdown:
            print(f"\nMarkdown report: {Path(args.markdown).resolve()}")

    if report.delta < -args.max_drop:
        return 1
    if args.fail_on_new_errors and report.new_errors:
        return 1
    return 0


def _main_scan(argv: list[str]) -> int:
    args = build_scan_parser().parse_args(argv)
    root = Path(args.path)
    if not root.exists() or not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    report = analyze(root)

    if args.html:
        out = Path(args.html)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_report(report), encoding="utf-8")
    if args.badge:
        out = Path(args.badge)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(badge_svg(report), encoding="utf-8")
    if args.sarif:
        out = Path(args.sarif)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(sarif_report(report), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print_report(report)
        if args.html:
            print(f"\nHTML report: {Path(args.html).resolve()}")
        if args.badge:
            print(f"Badge: {Path(args.badge).resolve()}")
        if args.sarif:
            print(f"SARIF report: {Path(args.sarif).resolve()}")

    if args.fail_under is not None and report.score < args.fail_under:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "compare":
        return _main_compare(args[1:])
    return _main_scan(args)


if __name__ == "__main__":
    raise SystemExit(main())
