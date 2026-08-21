from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .config import ConfigError, Policy, load_policy
from .gitdiff import GitError, baseline_worktree, repository_root
from .initializer import InitError, initialize_repository
from .regression import compare, markdown_report
from .rules import RULES, get_rule
from .sarif import sarif_report
from .scanner import analyze, badge_svg, html_report

RESET = "\033[0m"
BOLD = "\033[1m"
COLORS = {"error": "\033[31m", "warning": "\033[33m", "info": "\033[36m"}
GRADE_COLORS = {"A": "\033[32m", "B": "\033[32m", "C": "\033[33m", "D": "\033[33m", "F": "\033[31m"}

TOP_LEVEL_HELP = """usage:
  agent-config-score [PATH] [scan options]
  agent-config-score init [PATH] [options]
  agent-config-score rules [RULE_ID] [options]
  agent-config-score diff BASE_REF [options]
  agent-config-score compare BASE HEAD [options]

Score and regression-check AI coding-agent instruction files.

commands:
  init       Add a repository policy and GitHub Actions workflow safely.
  rules      List or explain the stable AgentConfigScore rule catalog.
  diff       Compare a Git ref with the current working tree.
  compare    Compare two already checked-out repository trees.

common examples:
  agent-config-score init
  agent-config-score rules
  agent-config-score rules curl-pipe-shell
  agent-config-score .
  agent-config-score diff origin/main
  agent-config-score compare ../repo-base .

Run `agent-config-score <command> --help` for command-specific options.
Use `agent-config-score --version` to print the version.
"""


def _supports_color() -> bool:
    return sys.stdout.isatty()


def _c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}" if _supports_color() else text


def _print_suppressed(report) -> None:
    if not report.suppressed_findings:
        return
    print(f"\nSuppressed findings: {len(report.suppressed_findings)}")
    for item in report.suppressed_findings:
        finding = item.finding
        suppression = item.suppression
        location = finding.file + (f":{finding.line}" if finding.line else "")
        print(f"~ SUPPRESSED {finding.code:20} {finding.message}")
        print(f"             {location}")
        print(f"             reason: {suppression.reason}")
        print(f"             expires: {suppression.expires.isoformat()}")
        if suppression.paths:
            print(f"             paths: {', '.join(suppression.paths)}")


def print_report(report) -> None:
    grade = _c(report.grade, GRADE_COLORS[report.grade])
    print(f"\n{BOLD if _supports_color() else ''}AgentConfigScore{RESET if _supports_color() else ''}  {grade}  {report.score}/100")
    print(
        f"Files: {len(report.files)}   Estimated tokens: {report.estimated_tokens:,}   "
        f"Duplication: {report.duplicate_ratio:.0%}   Suppressed: {len(report.suppressed_findings)}\n"
    )
    if not report.findings:
        print(_c("✓ No active findings", "\033[32m"))
    else:
        for f in report.findings:
            icon = {"error": "✖", "warning": "!", "info": "i"}.get(f.severity, "-")
            loc = f.file + (f":{f.line}" if f.line else "")
            prefix = _c(f"{icon} {f.severity.upper():7}", COLORS.get(f.severity, ""))
            print(f"{prefix} {f.code:20} {f.message}")
            print(f"           {loc}")
    _print_suppressed(report)


def print_regression(report) -> None:
    sign = "+" if report.delta > 0 else ""
    print(
        f"\n{BOLD if _supports_color() else ''}AgentConfigScore regression{RESET if _supports_color() else ''}  "
        f"{report.base.grade} {report.base.score} → {report.head.grade} {report.head.score} ({sign}{report.delta})"
    )
    print(
        f"New findings: {len(report.new_findings)}   Resolved: {len(report.resolved_findings)}   "
        f"Suppressed: {len(report.head.suppressed_findings)}\n"
    )
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
        print("✓ No active agent-config changes detected")
    _print_suppressed(report.head)


def build_scan_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent-config-score", description="Score and audit coding-agent instruction files.")
    p.add_argument("path", nargs="?", default=".", help="Repository path (default: current directory)")
    p.add_argument("--json", action="store_true", help="Print JSON instead of text")
    p.add_argument("--html", metavar="FILE", help="Write a self-contained HTML report")
    p.add_argument("--badge", metavar="FILE", help="Write an SVG score badge")
    p.add_argument("--sarif", metavar="FILE", help="Write a SARIF 2.1.0 report for GitHub code scanning")
    p.add_argument("--fail-under", type=int, default=None, metavar="N", help="Override the repository policy score floor")
    return p


def build_init_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-config-score init",
        description="Initialize AgentConfigScore policy and CI files without overwriting existing files by default.",
    )
    p.add_argument("path", nargs="?", default=".", help="Repository directory (default: current directory)")
    p.add_argument("--no-workflow", action="store_true", help="Create only .agentconfigscore.json")
    p.add_argument("--force", action="store_true", help="Overwrite conflicting generated files")
    p.add_argument("--dry-run", action="store_true", help="Show the initialization plan without writing files")
    return p


def build_rules_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-config-score rules",
        description="List all stable rule IDs or explain one rule in detail.",
    )
    p.add_argument("rule_id", nargs="?", help="Optional rule ID, for example: curl-pipe-shell")
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return p


def _add_regression_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="Print JSON instead of text")
    p.add_argument("--markdown", metavar="FILE", help="Write a Markdown regression summary")
    p.add_argument("--max-drop", type=int, default=None, metavar="N", help="Override the repository policy score-drop budget")
    p.add_argument(
        "--fail-on-new-errors",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override whether newly introduced error findings fail the check",
    )


def build_compare_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-config-score compare",
        description="Compare two repository trees and fail only when agent configuration regresses.",
    )
    p.add_argument("base", help="Baseline repository directory")
    p.add_argument("head", help="Candidate repository directory")
    _add_regression_options(p)
    return p


def build_diff_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-config-score diff",
        description="Compare a Git ref with the current working tree without manually creating a baseline checkout.",
    )
    p.add_argument("base_ref", help="Baseline Git branch, tag, or commit (for example: origin/main)")
    p.add_argument("--path", default=".", metavar="DIR", help="Path inside the Git repository (default: current directory)")
    _add_regression_options(p)
    return p


def _existing_dir(value: str) -> Path | None:
    path = Path(value)
    return path if path.exists() and path.is_dir() else None


def _resolve_regression_policy(args, policy: Policy) -> None:
    args.max_drop = policy.max_drop if args.max_drop is None else args.max_drop
    args.fail_on_new_errors = policy.fail_on_new_errors if args.fail_on_new_errors is None else args.fail_on_new_errors
    if args.max_drop < 0:
        raise ConfigError("--max-drop must be >= 0")


def _finish_regression(report, args) -> int:
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


def _main_init(argv: list[str]) -> int:
    args = build_init_parser().parse_args(argv)
    try:
        changes = initialize_repository(
            Path(args.path),
            include_workflow=not args.no_workflow,
            force=args.force,
            dry_run=args.dry_run,
        )
    except InitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for change in changes:
        if change.action == "unchanged":
            label = "unchanged"
        elif args.dry_run:
            label = f"would {change.action}"
        else:
            label = f"{change.action}d" if change.action == "create" else "overwritten"
        print(f"{label:12} {change.path.as_posix()}")

    if args.dry_run:
        print("Dry run: no files written.")
    else:
        print("\nAgentConfigScore initialized. Review and commit the generated files.")
    return 0


def _main_rules(argv: list[str]) -> int:
    args = build_rules_parser().parse_args(argv)
    if args.rule_id:
        rule = get_rule(args.rule_id)
        if rule is None:
            print(f"error: unknown rule ID: {args.rule_id}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(rule.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(rule.code)
            print(f"Severity: {rule.severity}")
            print(f"Category: {rule.category}")
            print(f"Penalty:  {rule.penalty}")
            print(f"Summary:  {rule.summary}")
            print(f"\n{rule.description}")
        return 0

    if args.json:
        print(json.dumps([rule.to_dict() for rule in RULES], indent=2, ensure_ascii=False))
        return 0

    print(f"{'RULE ID':22} {'SEVERITY':8} {'CATEGORY':8} {'PENALTY':7} SUMMARY")
    for rule in RULES:
        print(f"{rule.code:22} {rule.severity:8} {rule.category:8} {rule.penalty:7} {rule.summary}")
    print(f"\n{len(RULES)} rules. Run `agent-config-score rules RULE_ID` for details.")
    return 0


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

    try:
        policy = load_policy(base)
        load_policy(head)  # Validate candidate config, but never let it govern its own PR.
        _resolve_regression_policy(args, policy)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return _finish_regression(compare(base, head, suppressions=policy.suppressions), args)


def _main_diff(argv: list[str]) -> int:
    args = build_diff_parser().parse_args(argv)

    try:
        repo = repository_root(Path(args.path))
        with baseline_worktree(repo, args.base_ref) as (base, sha):
            policy = load_policy(base)
            load_policy(repo)  # Validate candidate config without trusting it yet.
            _resolve_regression_policy(args, policy)
            report = compare(base, repo, suppressions=policy.suppressions)
        report.base.root = f"git:{args.base_ref}@{sha[:12]}"
        report.head.root = str(repo)
    except (GitError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return _finish_regression(report, args)


def _main_scan(argv: list[str]) -> int:
    args = build_scan_parser().parse_args(argv)
    root = Path(args.path)
    if not root.exists() or not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    try:
        policy = load_policy(root)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    fail_under = policy.fail_under if args.fail_under is None else args.fail_under
    if fail_under is not None and not 0 <= fail_under <= 100:
        print("error: --fail-under must be between 0 and 100", file=sys.stderr)
        return 2

    report = analyze(root, suppressions=policy.suppressions)

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

    if fail_under is not None and report.score < fail_under:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--version"] or args == ["-V"]:
        print(f"AgentConfigScore {__version__}")
        return 0
    if args == ["--help"] or args == ["-h"]:
        print(TOP_LEVEL_HELP, end="")
        return 0
    if args and args[0] == "init":
        return _main_init(args[1:])
    if args and args[0] == "rules":
        return _main_rules(args[1:])
    if args and args[0] == "compare":
        return _main_compare(args[1:])
    if args and args[0] == "diff":
        return _main_diff(args[1:])
    return _main_scan(args)


if __name__ == "__main__":
    raise SystemExit(main())
