from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent-config-score", description="Score and audit coding-agent instruction files.")
    p.add_argument("path", nargs="?", default=".", help="Repository path (default: current directory)")
    p.add_argument("--json", action="store_true", help="Print JSON instead of text")
    p.add_argument("--html", metavar="FILE", help="Write a self-contained HTML report")
    p.add_argument("--badge", metavar="FILE", help="Write an SVG score badge")
    p.add_argument("--fail-under", type=int, default=None, metavar="N", help="Exit non-zero when score is below N")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print_report(report)
        if args.html:
            print(f"\nHTML report: {Path(args.html).resolve()}")
        if args.badge:
            print(f"Badge: {Path(args.badge).resolve()}")

    if args.fail_under is not None and report.score < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
