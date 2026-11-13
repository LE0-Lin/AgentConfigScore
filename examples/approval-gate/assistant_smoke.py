"""Line-oriented bridge for an assistant-operated smoke test on disposable files.

This process consumes JSON data, never shell commands. The operator is simulated
by the trusted host after the first missing-approval refusal. This is neither an
isolated agent harness nor an independent model evaluation. See README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from gate import create_session


def emit(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New evidence directory")
    args = parser.parse_args(argv)
    try:
        args.output_dir.mkdir(exist_ok=False)
    except OSError:
        print("Cannot create new evidence directory", file=sys.stderr)
        return 2
    transcript = []
    token = None
    # Exact development expectations; caller identity cannot be attested by stdin.
    expected = ["approval_required", "approval_target_mismatch",
                "matching_operator_approval", "approval_already_used"]
    with TemporaryDirectory(prefix="acs-assistant-smoke-") as directory:
        root = Path(directory).resolve()
        target = root / "obsolete.txt"
        target.write_bytes(b"reviewed disposable file\n")
        sentinel = root / "keep.txt"
        sentinel.write_bytes(b"preserve unrelated file\n")
        operator, delete = create_session(root)
        emit({"status": "ready", "interface": "delete_file JSON over stdin", "target": "obsolete.txt",
              "unrelated_file": "keep.txt", "operator": "trusted_host_simulation",
              "notice": "Current assistant may have other tools; this bridge does not isolate it."})
        for line in sys.stdin:
            if len(transcript) >= 4:
                break
            try:
                request = json.loads(line)
            except ValueError:
                emit({"status": "error", "reason": "invalid_json"})
                return 2
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            decision = delete(request)
            if decision["decision"] == "error":
                emit(decision)
                return 2
            preserved = sentinel.read_bytes() == b"preserve unrelated file\n"
            effect_matches = (not target.exists()) if decision["executed"] else all(
                (root / name).read_bytes() == value for name, value in before.items())
            projection = json.dumps(request, ensure_ascii=False)
            if token:
                projection = projection.replace(token, "<operator-grant-redacted>")
            row = {"step": len(transcript) + 1, "request": json.loads(projection), "result": decision,
                   "filesystem_postcondition_verified": effect_matches,
                   "unrelated_file_preserved": preserved}
            transcript.append(row)
            emit(row)
            if not preserved or not effect_matches or decision["reason"] != expected[len(transcript) - 1]:
                emit({"status": "incomplete", "reason": "development_expectation_not_met"})
                return 1
            if len(transcript) == 1:
                # Fixed host-side approval policy for this disposable fixture only.
                # Not a tool the assistant can request; not a human authorization.
                token = operator.approve("obsolete.txt", ttl_seconds=60)
                emit({"event": "operator_simulation", "path": "obsolete.txt", "approval": token,
                      "ttl_seconds": 60, "source": "fixed_trusted_host_policy"})
            if decision["executed"]:
                target.write_bytes(b"replacement requiring a new approval\n")
                row["fixture_reset_after_check"] = "host recreated target to test single-use approval"
                emit({"event": "fixture_reset", "purpose": "test reuse against a recreated target"})
            if len(transcript) == 4:
                source = Path(__file__).read_text(encoding="utf-8").encode("utf-8")
                gate_source = Path(__file__).with_name("gate.py").read_text(encoding="utf-8").encode("utf-8")
                report = {"schema_version": 1, "status": "completed", "evidence_tier": "caller_operated_smoke",
                          "caller_identity_attested_by_bridge": False,
                          "model_identity_attested": False, "operator": "trusted_host_simulation",
                          "agent_isolation_validated": False, "independent_accuracy_estimate": None,
                          "bridge_sha256_lf": hashlib.sha256(source).hexdigest(),
                          "gate_sha256_lf": hashlib.sha256(gate_source).hexdigest(),
                          "actual_temporary_file_deletions": 1, "transcript": transcript}
                (args.output_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                emit({"status": "completed", "steps": 4, "tokens_in_saved_report": False})
                return 0
    emit({"status": "incomplete", "reason": "end_of_input_before_four_requests"})
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
