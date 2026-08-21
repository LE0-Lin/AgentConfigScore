from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .cli import main as cli_main
from .doctor import diagnose


TOP_LEVEL_HELP = """usage:
  agent-config-score [PATH] [scan options]
  agent-config-score init [PATH] [options]
  agent-config-score doctor [PATH] [options]
  agent-config-score rules [RULE_ID] [options]
  agent-config-score diff BASE_REF [options]
  agent-config-score compare BASE HEAD [options]

Score, validate, and regression-check AI coding-agent instruction files.

commands:
  init       Add a repository policy and GitHub Actions workflow safely.
  doctor     Validate AgentConfigScore repository integration and readiness.
  rules      List or explain the stable AgentConfigScore rule catalog.
  diff       Compare a Git ref with the current working tree.
  compare    Compare two already checked-out repository trees.

common examples:
  agent-config-score init
  agent-config-score doctor
  agent-config-score rules curl-pipe-shell
  agent-config-score .
  agent-config-score diff origin/main

Run `agent-config-score <command> --help` for command-specific options.
Use `agent-config-score --version` to print the version.
"""


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
        symbols = {"pass": "✓", "warning": "!", "error": "✖"}
        for check in report.checks:
            print(f"{symbols.get(check.status, '-')} {check.name:14} {check.message}")
        print(f"\n{report.errors} error(s), {report.warnings} warning(s)")

    return 0 if report.ok else 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--version"] or args == ["-V"]:
        print(f"AgentConfigScore {__version__}")
        return 0
    if args == ["--help"] or args == ["-h"]:
        print(TOP_LEVEL_HELP, end="")
        return 0
    if args and args[0] == "doctor":
        return _main_doctor(args[1:])
    return cli_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
