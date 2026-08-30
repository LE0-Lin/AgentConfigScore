from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .cli import main as cli_main
from .doctor import diagnose
from .gitdiff import GitError, detect_base_ref, repository_root


TOP_LEVEL_HELP = """usage:
  agent-config-score [PATH] [scan options]
  agent-config-score init [PATH] [options]
  agent-config-score doctor [PATH] [options]
  agent-config-score rules [RULE_ID] [options]
  agent-config-score history [PATH] [options]
  agent-config-score diff [BASE_REF] [options]
  agent-config-score compare BASE HEAD [options]

Score, validate, and regression-check AI coding-agent instruction files.

commands:
  init       Add a repository policy and GitHub Actions workflow safely.
  doctor     Validate AgentConfigScore repository integration and readiness.
  rules      List or explain the stable AgentConfigScore rule catalog.
  history    Show locally recorded score snapshots and overall trend.
  diff       Compare a Git baseline with the current working tree.
  compare    Compare two already checked-out repository trees.

common examples:
  agent-config-score init
  agent-config-score doctor
  agent-config-score rules curl-pipe-shell
  agent-config-score .
  agent-config-score history
  agent-config-score diff
  agent-config-score diff origin/main

`diff` auto-detects a local default branch when BASE_REF is omitted. It never fetches.
Run `agent-config-score <command> --help` for command-specific options.
Use `agent-config-score --version` to print the version.
"""


_DIFF_VALUE_OPTIONS = {"--path", "--markdown", "--max-drop"}


def _configure_console_streams() -> None:
    """Prevent unsupported terminal encodings from crashing the installed CLI."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(errors="backslashreplace")
            except (AttributeError, ValueError):
                pass


def _doctor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-config-score doctor",
        description="Validate AgentConfigScore repository integration without modifying files or using the network.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Repository directory (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def _main_doctor(argv: list[str]) -> int:
    args = _doctor_parser().parse_args(argv)
    report = diagnose(Path(args.path))

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print("AgentConfigScore doctor")
        print(f"Repository: {report.root}\n")
        symbols = {"pass": "OK", "warning": "!", "error": "X"}
        for check in report.checks:
            print(f"{symbols.get(check.status, '-'):2} {check.name:14} {check.message}")
        print(f"\n{report.errors} error(s), {report.warnings} warning(s)")

    return 0 if report.ok else 1


def _diff_invocation(argv: list[str]) -> tuple[bool, Path]:
    """Return whether BASE_REF is explicit and the repository path option."""
    path = Path(".")
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--":
            return index + 1 < len(argv), path
        if token == "--path":
            if index + 1 < len(argv):
                path = Path(argv[index + 1])
            index += 2
            continue
        if token.startswith("--path="):
            path = Path(token.split("=", 1)[1])
            index += 1
            continue
        if token in _DIFF_VALUE_OPTIONS:
            index += 2
            continue
        if any(token.startswith(option + "=") for option in _DIFF_VALUE_OPTIONS):
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        return True, path
    return False, path


def _main_diff(argv: list[str]) -> int:
    if "--help" in argv or "-h" in argv:
        return cli_main(["diff", *argv])

    explicit_ref, path = _diff_invocation(argv)
    if explicit_ref:
        return cli_main(["diff", *argv])

    try:
        repo = repository_root(path)
        base_ref = detect_base_ref(repo)
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    return cli_main(["diff", base_ref, *argv])


def main(argv: list[str] | None = None) -> int:
    _configure_console_streams()
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--version"] or args == ["-V"]:
        print(f"AgentConfigScore {__version__}")
        return 0
    if args == ["--help"] or args == ["-h"]:
        print(TOP_LEVEL_HELP, end="")
        return 0
    if args and args[0] == "doctor":
        return _main_doctor(args[1:])
    if args and args[0] == "diff":
        return _main_diff(args[1:])
    return cli_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
