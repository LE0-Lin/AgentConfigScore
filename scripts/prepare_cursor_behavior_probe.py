#!/usr/bin/env python3
"""Prepare a separate synthetic Cursor behavior probe, not a loading oracle.

Random marker keys and ACS predictions stay outside the workspace. The user
operates Cursor; this helper never starts a model or uploads files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import subprocess

from prepare_cursor_native_probe import HOOK, RULES, CASES


FROZEN_SOURCE = "d6b3b079d6a8ab0d870020abe5f6489b59536c5a6602e2083dfc80b0c97d1ed5"


def prepare(root: Path, evidence: Path, python: Path) -> dict:
    root, evidence = root.resolve(), evidence.resolve()
    if (root.exists() or evidence.exists() or root.is_relative_to(evidence)
            or evidence.is_relative_to(root)):
        raise ValueError("use new, separate workspace and evidence directories")
    markers = {name: "ACS_" + name.removesuffix(".mdc").replace("-", "_").upper()
               + "_" + secrets.token_hex(8) for name in RULES}
    files = {
        "capture_native.py": HOOK,
        "src/api/service.py": "def health():\n    return 'ok'\n",
        "src/web/app.ts": "export const status = 'ok';\n",
        "index.ts": "export const rootStatus = 'ok';\n",
    }
    for name, text in RULES.items():
        metadata = text[:text.index("---", 3) + 3]
        files[".cursor/rules/" + name] = (metadata + "\nWhen the user message contains NATIVE_BEHAVIOR_V1, "
            "include the exact marker `" + markers[name] + "` once in your final answer. "
            "Do not search for additional marker sources.\n")
    command = f'"{python.absolute().as_posix()}" -I "{(root / "capture_native.py").as_posix()}"'
    files[".cursor/hooks.json"] = json.dumps({"version": 1, "hooks": {
        event: [{"command": command + " " + event}] for event in ("beforeSubmitPrompt", "beforeReadFile")
    }}, indent=2) + "\n"
    root.mkdir(parents=True)
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    rows = []
    for case in CASES:
        command = [str(python.absolute()), "-I", "-X", "utf8", "-m", "agent_config_score.cli",
                   "scope", str(root), *[arg for target in case["targets"] for arg in ("--target", target)], "--json"]
        run = subprocess.run(command, cwd=root, capture_output=True, encoding="utf-8", timeout=45)
        if run.returncode:
            raise ValueError("frozen scope prediction failed; workspace preparation is incomplete")
        prediction = json.loads(run.stdout)
        tool = prediction["tool"]
        if tool["version"] != "0.26.1" or tool["source_fingerprint"]["sha256"] != FROZEN_SOURCE:
            raise ValueError("use the unchanged published v0.26.1 installation")
        targets = ", ".join(case["targets"])
        prompt = (f"NATIVE_BEHAVIOR_V1 {case['id']}. Read only the attached {targets}. "
                  "Reply with its declared name(s) and any probe markers required by the project rules. "
                  "Do not inspect other files, search, edit, or run shell commands.")
        rows.append({"id": case["id"], "targets": case["targets"], "prompt": prompt,
                     "acs_prediction": prediction})
    manifest = {"schema_version": 1, "status": "prepared_no_native_behavior_results",
                "prepared_at_utc": datetime.now(timezone.utc).isoformat(), "markers": markers,
                "inputs_sha256": {name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()},
                "cases": rows,
                "manual_positive_control": "Explicitly select @always.mdc. Send NATIVE_BEHAVIOR_V1 manual-control. Reply only with the probe marker required by this rule. Do not inspect other files, search, edit, or run commands.",
                "interpretation": "Marker appearance is observed behavior consistent with access to a rule body, not a complete rule-attachment trace. Missing markers can be noncompliance, not absence. Unexpected file/rule reads confound interpretation. Keep client version, UI evidence, hook limits, failures and all replies. This is not independent accuracy.",
                "operator": "user-controlled UI; separate fresh chat per case; explicitly attach target file chips only, without manually attaching rules in automatic cases"}
    evidence.mkdir(parents=True)
    with (evidence / "behavior-manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.workspace, args.evidence_dir, args.python)
    print(f"Prepared {len(result['cases'])} behavioral contexts and one manual control. No model run or compatibility verdict.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
