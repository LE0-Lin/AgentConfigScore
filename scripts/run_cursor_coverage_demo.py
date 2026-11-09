"""Replay an installed tool on synthetic Cursor attachment changes, offline.

No Cursor/model is invoked. This checks the declared static model, not native
loading fidelity, detection accuracy or user adoption.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "cursor-scope-impact"
CASES = (("narrowed", 1, 1, 0), ("repaired", 0, 0, 0), ("renamed", 0, 0, 0),
         ("uncertain", 1, 0, 2), ("base", 0, 0, 0))


def replay(python: Path) -> dict:
    identity = None
    rows = []
    manifest = {}
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    with TemporaryDirectory(prefix="acs-coverage-demo-") as directory:
        def invoke(args, expected=0):
            result = subprocess.run([str(python), "-I", "-m", "agent_config_score", *args, "--json"],
                                    cwd=directory, env=env, capture_output=True, text=True,
                                    encoding="utf-8", timeout=45)
            if result.returncode != expected or result.stderr:
                raise ValueError("Demo command did not complete as expected; install a source build with scope coverage")
            data = json.loads(result.stdout)
            if identity is not None and data.get("tool") != identity:
                raise ValueError("Demo mixed installed tool identities")
            return data

        base = FIXTURE / "base"
        body = (base / ".cursor/rules/policy.mdc").read_text(encoding="utf-8").split("---", 2)[2]
        for name, expected_exit, losses, unknowns in CASES:
            head = FIXTURE / name
            rules = list((head / ".cursor/rules").glob("*.mdc"))
            if len(rules) != 1 or rules[0].read_text(encoding="utf-8").split("---", 2)[2] != body:
                raise ValueError("Demo must preserve identical instruction bodies")
            for path in sorted(head.rglob("*")):
                if path.is_file():
                    manifest[path.relative_to(FIXTURE).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
            report = invoke(["scope", "coverage", str(base), str(head), "--under", "src",
                             "--fail-on-lost-directives", "--fail-on-unknown"], expected_exit)
            summary = report["summary"]
            if (summary["files"], summary["files_with_losses"], summary["files_with_unknown"]) != (2, losses, unknowns):
                raise ValueError("Coverage demo no longer matches its documented development expectation")
            if identity is not None and identity != report["tool"]:
                raise ValueError("Demo mixed installed tool identities")
            identity = report["tool"]
            if identity["source_fingerprint"]["sha256"] is None:
                raise ValueError("Demo requires a complete source identity")
            scores = [invoke([str(root)])["score"] for root in (base, head)]
            if scores != [100, 100]:
                raise ValueError("Standalone score control changed; review the demo")
            rows.append({"case": name, "exit": expected_exit, "standalone_scores": scores, "coverage": report})
        joint = invoke(["scope", "compare", str(base), str(FIXTURE / "narrowed"),
                        "--target", "src/api/service.py", "--target", "src/web/app.ts",
                        "--fail-on-lost-directives", "--fail-on-unknown"])
        if joint["tool"] != identity or joint["summary"]["recognized_active_losses"] != 0:
            raise ValueError("Joint-context control changed; review the demo")
    return {"schema_version": 1, "evidence_tier": "synthetic_development_demo", "tool": identity,
            "native_cursor_run": False, "independent_accuracy_estimate": None,
            "instruction_body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "fixture_files_sha256": manifest, "joint_context_control": joint,
            "cases": rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable), help="Python with the tool already installed")
    parser.add_argument("--output", type=Path, help="Create a new JSON report; existing files are preserved")
    args = parser.parse_args(argv)
    try:
        report = replay(args.python.absolute())
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(text)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"Coverage demo failed: {exc}", file=sys.stderr)
        return 2
    if args.output is None:
        print(text, end="")
    else:
        print("Coverage demo passed: five synthetic cases and the joint-context control. Native Cursor validation remains pending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
