"""Replay static configuration checks and a host-side deletion approval example.

Scripted development scenarios; no model, network, or external repository calls.
Actual deletions are restricted to fresh TemporaryDirectory workspaces.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/approval-gate"
SPEC = importlib.util.spec_from_file_location("approval_demo_gate", EXAMPLE / "gate.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    # Repository evidence hashes use normalized text for cross-platform checkouts.
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def static_replay(python: Path) -> dict:
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(name, None)
    env.update(PYTHONNOUSERSITE="1", PYTHONIOENCODING="utf-8")
    identity = None
    with TemporaryDirectory(prefix="acs-approval-static-") as cwd:
        def invoke(args, expected):
            nonlocal identity
            result = subprocess.run([str(python), "-I", "-X", "utf8", "-m", "agent_config_score",
                                     *args, "--json"], cwd=cwd, env=env, capture_output=True,
                                    text=True, encoding="utf-8", timeout=45)
            require(result.returncode == expected and not result.stderr,
                    "Installed ACS command did not complete with its expected exit")
            data = json.loads(result.stdout)
            require(data.get("tool", {}).get("source_fingerprint", {}).get("sha256"),
                    "Missing installed source identity")
            if identity is None:
                identity = data["tool"]
            require(identity == data["tool"], "Mixed installed tool identities")
            return data

        base = EXAMPLE / "config/base"
        rows = []
        body = (base / ".cursor/rules/deletion.mdc").read_text(encoding="utf-8").split("---", 2)[2]
        for case, expected, losses in (("narrowed", 1, 1), ("repaired", 0, 0)):
            head = EXAMPLE / "config" / case
            require((head / ".cursor/rules/deletion.mdc").read_text(encoding="utf-8").split("---", 2)[2] == body,
                    "Static demonstration must preserve the instruction body")
            report = invoke(["scope", "compare", str(base), str(head), "--target", "workspace/obsolete.txt",
                             "--fail-on-lost-directives", "--fail-on-unknown"], expected)
            summary = report["summary"]
            require(report["status"] == "completed" and not summary["has_unknown"]
                    and summary["recognized_active_losses"] == losses,
                    "Static comparison disagrees with the development expectation")
            scores = [invoke([str(tree)], 0)["score"] for tree in (base, head)]
            require(scores == [100, 100], "Standalone score control changed")
            rows.append({"case": case, "exit": expected, "standalone_scores": scores, "report": report})
    return {"tool": identity, "cases": rows}


def execution_replay() -> list:
    rows = []
    cases = ("missing_approval", "self_approval", "invented_token", "expired", "wrong_target",
             "changed_content", "replaced_file", "different_session", "outside_workspace",
             "unregistered_tool", "authorized", "replay")
    expected = ("approval_required", "invalid_request_schema", "invalid_approval", "approval_expired",
                "approval_target_mismatch", "approved_state_changed", "approved_state_changed",
                "invalid_approval", "invalid_relative_path", "unregistered_tool",
                "matching_operator_approval", "approval_already_used")
    for case, reason in zip(cases, expected):
        with TemporaryDirectory(prefix="acs-approval-execution-") as directory:
            parent = Path(directory).resolve()
            root = parent / "workspace"
            root.mkdir()
            target = root / "obsolete.txt"
            target.write_bytes(b"reviewed content\n")
            other = root / "other.txt"
            other.write_bytes(b"other content\n")
            outside = parent / "outside.txt"
            outside.write_bytes(b"preserve outside\n")
            clock = [100.0]
            # Trusted harness simulates the operator. This is NOT human-approval evidence.
            operator, delete = GATE.create_session(root, clock=lambda: clock[0])
            token = operator.approve("obsolete.txt", ttl_seconds=1)
            request = {"tool": "delete_file", "path": "obsolete.txt", "approval": token}
            if case == "missing_approval":
                request.pop("approval")
            elif case == "self_approval":
                request.pop("approval")
                request["approved"] = True
            elif case == "invented_token":
                request["approval"] = "invented-token"
            elif case == "expired":
                clock[0] = 101.0
            elif case == "wrong_target":
                request["path"] = "other.txt"
            elif case == "changed_content":
                target.write_bytes(b"content changed after review\n")
            elif case == "replaced_file":
                replacement = root / "replacement.txt"
                replacement.write_bytes(target.read_bytes())
                os.replace(replacement, target)
            elif case == "different_session":
                _, delete = GATE.create_session(root, clock=lambda: clock[0])
            elif case == "outside_workspace":
                request["path"] = "../outside.txt"
            elif case == "unregistered_tool":
                request["tool"] = "shell"
            elif case == "replay":
                first = delete(request)
                require(first["executed"] and not target.exists(), "Replay setup deletion failed")
                target.write_bytes(b"new file, new intent\n")
            before = target.read_bytes()
            result = delete(request)
            require(result["reason"] == reason, "Execution scenario disagrees with expectation: " + case)
            successful = case == "authorized"
            require(result["decision"] == ("executed" if successful else "denied")
                    and result["executed"] == successful, "Unexpected execution status: " + case)
            require((not target.exists()) if successful else target.read_bytes() == before,
                    "Target filesystem postcondition failed: " + case)
            require(other.read_bytes() == b"other content\n" and outside.read_bytes() == b"preserve outside\n",
                    "Unrelated-file preservation failed: " + case)
            # Persist neither tokens nor private temp paths.
            rows.append({"case": case, **result, "filesystem_postcondition_verified": True,
                         "unrelated_files_preserved": True})
    return rows


def replay(python: Path) -> dict:
    static = static_replay(python)
    execution = execution_replay()
    inputs = [EXAMPLE / "gate.py", EXAMPLE / "try_gate.py", Path(__file__).resolve(),
              ROOT / "tests/test_approval_gate_demo.py",
              *sorted((EXAMPLE / "config").rglob("*.txt")),
              *sorted((EXAMPLE / "config").rglob("*.mdc"))]
    return {"schema_version": 1, "evidence_tier": "synthetic_development_demo",
            "operator": "trusted_harness_simulation", "live_agent_run": False,
            "independent_accuracy_estimate": None,
            "host": {"system": platform.system(), "python": platform.python_version()},
            "text_inputs_sha256_lf": {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs},
            "static": static, "execution": execution,
            "actual_temporary_file_deletions": 2,
            "limitations": ["Static analysis predicts declared attachment; it does not observe this execution.",
                            "The gate is separate example host code, not an ACS runtime enforcement feature.",
                            "The host owns a stable local workspace and exposes only the registered delete tool.",
                            "Arbitrary host code, shell access and concurrent filesystem attackers are out of scope."]}


def markdown(report) -> str:
    lines = ["# Deletion approval replay", "", "Synthetic development scenarios; operator approvals are simulated by the trusted harness.",
             "No live model was called. These results are not an accuracy or real-world safety estimate.", "",
             f"Installed ACS: {report['static']['tool']['version']}",
             f"Source fingerprint: `{report['static']['tool']['source_fingerprint']['sha256']}`", "",
             "| Configuration change | Scores (base/head) | Lost active directives | Review exit |",
             "|---|---|---|---|"]
    for row in report["static"]["cases"]:
        lines.append(f"| {row['case']} | {row['standalone_scores']} | {row['report']['summary']['recognized_active_losses']} | {row['exit']} |")
    lines += ["", "| Scripted tool request | Decision | Reason | Filesystem checked |", "|---|---|---|---|"]
    for row in report["execution"]:
        lines.append(f"| {row['case']} | {row['decision']} | `{row['reason']}` | yes |")
    lines += ["", "Two real file deletions occurred inside disposable temporary directories: the authorized case and the replay setup.",
              "Rejected requests preserved the target; every scenario preserved the unrelated-file sentinels.", "",
              "## Boundaries", "", *["- " + item for item in report["limitations"]], ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable), help="Python with ACS already installed")
    parser.add_argument("--output-dir", type=Path, required=True, help="New report directory; existing paths are refused")
    args = parser.parse_args(argv)
    try:
        # Reserve before effects; an existing report is never overwritten.
        args.output_dir.mkdir(parents=False, exist_ok=False)
        report = replay(args.python.absolute())
        (args.output_dir / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.output_dir / "result.md").write_text(markdown(report), encoding="utf-8")
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f"Approval demo failed ({type(exc).__name__}); no completed evidence should be inferred.", file=sys.stderr)
        return 2
    print("Completed: 2 static comparisons; 12 scripted execution scenarios; filesystem postconditions verified.")
    print("Operator simulation; temporary files only. Read result.md and result.json for boundaries and source identities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
