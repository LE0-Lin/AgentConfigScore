#!/usr/bin/env python3
"""Create a new synthetic workspace for native Cursor observation; no model call.

Hooks retain allowlisted attachment metadata only, never prompt/file contents,
email, credentials or paths outside this synthetic workspace. The output is
observation preparation, not a compatibility result.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HOOK = r'''from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
event = sys.argv[1]
response = {"continue": True} if event == "beforeSubmitPrompt" else {"permission": "allow"}
try:
    raw = sys.stdin.buffer.read(1048577)
    if len(raw) > 1048576:
        raise ValueError("oversized input")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("expected object")
    attachments = []
    outside = unsupported = unusable = 0
    raw_attachments = data.get("attachments")
    entries = raw_attachments if isinstance(raw_attachments, list) else []
    entry_shapes = []
    safe_keys = {"type", "file_path", "filePath", "path", "uri", "name", "content"}
    for entry in entries:
        entry_shapes.append({"value_type": type(entry).__name__,
                             "known_keys": sorted(safe_keys.intersection(entry)) if isinstance(entry, dict) else []})
        if not isinstance(entry, dict) or entry.get("type") not in {"file", "rule"}:
            unsupported += 1
            continue
        try:
            target = Path(entry["file_path"]).resolve()
        except (KeyError, TypeError, ValueError, OSError):
            unusable += 1
            continue
        try:
            relative = target.relative_to(root).as_posix()
        except ValueError:
            outside += 1
            continue
        attachments.append({"type": entry["type"], "path": relative})
    known_input_keys = {"attachments", "prompt", "file_path", "content", "conversation_id", "session_id",
                        "hook_event_name", "cursor_version", "workspace_roots", "model", "tool_input"}
    record = {"schema_version": 2, "event": event,
              "captured_at_utc": datetime.now(timezone.utc).isoformat(),
              "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "known_input_field_types": {key: type(data[key]).__name__ for key in sorted(known_input_keys.intersection(data))},
              "attachments_field_present": "attachments" in data,
              "input_attachment_count": len(entries) if isinstance(raw_attachments, list) else None,
              "attachment_entry_shapes": entry_shapes,
              "unsupported_attachment_count": unsupported,
              "unusable_attachment_path_count": unusable,
              "reported_attachments": attachments,
              "outside_workspace_attachments_omitted": outside,
              "interpretation": "client-reported metadata at this hook, not model compliance or proof of complete context"}
    prompt = data.get("prompt")
    if isinstance(prompt, str):
        # Retain only a fixed synthetic case marker, never arbitrary prompt text.
        for marker in ("Probe api-only.", "Probe web-only.", "Probe joint.", "Probe root-ts.", "CAPTURE_CONTROL_V2"):
            if marker in prompt:
                record["recognized_probe_marker"] = marker
                break
    for name in ("conversation_id", "session_id"):
        if isinstance(data.get(name), str):
            record[name + "_sha256"] = hashlib.sha256(data[name].encode()).hexdigest()
    with (root / "native-observations.jsonl").open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, ensure_ascii=False) + "\n")
except Exception:
    # Collection failure must not disrupt the user's client. No raw input/error.
    print("Native probe could not retain this observation.", file=sys.stderr)
print(json.dumps(response))
'''

RULES = {
    "always.mdc": '---\nalwaysApply: true\n---\nUse concise factual answers in this synthetic probe.\n',
    "api.mdc": '---\nalwaysApply: false\nglobs: "src/**/*.py"\n---\nPreserve Python function names in this synthetic probe.\n',
    "web.mdc": '---\nalwaysApply: false\nglobs: "src/**/*.ts"\n---\nPreserve TypeScript export names in this synthetic probe.\n',
    "root-only.mdc": '---\nalwaysApply: false\nglobs: "*.ts"\n---\nPreserve root-level TypeScript filenames in this synthetic probe.\n',
}
CASES = [
    {"id": "api-only", "targets": ["src/api/service.py"],
     "prompt": "Probe api-only. Read @src/api/service.py and state its function name. Do not edit files or run shell commands."},
    {"id": "web-only", "targets": ["src/web/app.ts"],
     "prompt": "Probe web-only. Read @src/web/app.ts and state its export name. Do not edit files or run shell commands."},
    {"id": "joint", "targets": ["src/api/service.py", "src/web/app.ts"],
     "prompt": "Probe joint. Read @src/api/service.py and @src/web/app.ts and state their declared names. Do not edit files or run shell commands."},
    {"id": "root-ts", "targets": ["index.ts"],
     "prompt": "Probe root-ts. Read @index.ts and state its export name. Do not edit files or run shell commands."},
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable),
                        help="Python with the published agent-config-score==0.26.1 installed")
    args = parser.parse_args()
    root = args.output_dir.absolute()
    if root.exists():
        parser.error("requires a new workspace")
    python = args.python.absolute()
    root.mkdir(parents=True)
    files = {
        "capture_native.py": HOOK,
        "src/api/service.py": "def health():\n    return 'ok'\n",
        "src/web/app.ts": "export const status = 'ok';\n",
        "index.ts": "export const rootStatus = 'ok';\n",
        **{f".cursor/rules/{name}": text for name, text in RULES.items()},
    }
    command = f'"{python.as_posix()}" -I "{(root / "capture_native.py").as_posix()}"'
    hooks = {"version": 1, "hooks": {event: [{"command": command + " " + event}]
             for event in ("beforeSubmitPrompt", "beforeReadFile")}}
    files[".cursor/hooks.json"] = json.dumps(hooks, indent=2) + "\n"
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as output:
            output.write(text)
    predictions = []
    for case in CASES:
        completed = subprocess.run([str(python), "-I", "-X", "utf8", "-m", "agent_config_score.cli",
                                    "scope", str(root), *[arg for name in case["targets"] for arg in ("--target", name)],
                                    "--json"], cwd=root, capture_output=True, encoding="utf-8", timeout=45)
        if completed.returncode:
            raise ValueError("scope prediction failed; workspace is incomplete")
        result = json.loads(completed.stdout)
        if result["tool"]["version"] != "0.26.1":
            raise ValueError("use the frozen published version")
        predictions.append({"case": case, "prediction": result})
    manifest = {"schema_version": 1, "status": "prepared_no_native_observations",
                "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
                "case_instructions": "Use a fresh chat per case. Attach the listed files explicitly; ensure @ references resolve to file chips. Record client version and any global/team rule settings. No model answer is an attachment oracle. Retain disagreements. Absent rule entries in a hook are unobserved unless completeness is established.",
                "input_sha256": {name: hashlib.sha256(text.encode()).hexdigest() for name, text in files.items()},
                "predictions": predictions}
    with (root / "probe-manifest.json").open("x", encoding="utf-8") as output:
        json.dump(manifest, output, indent=2)
        output.write("\n")
    print(f"Prepared {len(CASES)} contexts; no native observation or model call has occurred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
