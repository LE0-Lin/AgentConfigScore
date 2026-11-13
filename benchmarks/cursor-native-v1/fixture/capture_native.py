from datetime import datetime, timezone
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
    record = {"schema_version": 3, "event": event,
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
    if event == "beforeReadFile" and isinstance(data.get("file_path"), str):
        try:
            record["observed_read_target"] = Path(data["file_path"]).resolve().relative_to(root).as_posix()
        except (ValueError, OSError):
            record["outside_or_invalid_read_target_omitted"] = True
    prompt = data.get("prompt")
    if isinstance(prompt, str):
        # Retain only a fixed synthetic case marker, never arbitrary prompt text.
        for marker in ("Probe api-only.", "Probe web-only.", "Probe joint.", "Probe root-ts.", "CAPTURE_CONTROL_V2",
                       "NATIVE_BEHAVIOR_V1 api-only", "NATIVE_BEHAVIOR_V1 web-only", "NATIVE_BEHAVIOR_V1 joint",
                       "NATIVE_BEHAVIOR_V1 root-ts", "NATIVE_BEHAVIOR_V1 manual-control"):
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
