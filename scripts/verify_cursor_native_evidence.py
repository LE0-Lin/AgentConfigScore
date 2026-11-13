#!/usr/bin/env python3
"""Verify retained native evidence offline, without Cursor or a model.

Integrity and internal agreement do not authenticate screenshots, reviewer
identity, complete context loading, or general accuracy. Disagreements remain
completed observations; exit zero means verification completed, not safety.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


BASE = Path(__file__).resolve().parents[1] / "benchmarks/cursor-native-v1"
MARKER = re.compile(r"ACS_[A-Z_]+_[0-9a-f]{16}")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def member(base: Path, name: str) -> Path:
    if (not isinstance(name, str) or "\\" in name or ":" in name
            or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts):
        raise ValueError("invalid evidence path")
    path = base / name
    if not path.resolve().is_relative_to(base.resolve()) or not path.is_file() or path.is_symlink():
        raise ValueError("evidence requires an in-tree regular file")
    return path


def assess(prepared: dict, observed: dict, events: list[dict]) -> dict:
    predictions = {case["id"]: case for case in prepared["cases"]}
    markers = prepared["markers"]
    cases = observed["cases"]
    expected_ids = set(predictions) | {"manual-control"}
    if len(cases) != 5 or {case["id"] for case in cases} != expected_ids:
        raise ValueError("exactly the registered four contexts and explicit control are required")
    if len({case["conversation_id_sha256"] for case in cases}) != len(cases):
        raise ValueError("fresh conversations are required")
    if len(set(markers.values())) != 4 or any(not MARKER.fullmatch(m) for m in markers.values()):
        raise ValueError("four distinct marker keys required")
    results = []
    for case in cases:
        cid = case["id"]
        visible = set(MARKER.findall(case["visible_final_excerpt"]))
        if visible != set(case["observed_visible_markers"]):
            raise ValueError("transcribed marker set is inconsistent")
        session = [e for e in events if e.get("conversation_id_sha256") == case["conversation_id_sha256"]]
        if len(session) != case["event_count"]:
            raise ValueError("case event count mismatch")
        prompts = [e for e in session if e["event"] == "beforeSubmitPrompt"]
        if len(prompts) != 1 or prompts[0].get("recognized_probe_marker") != f"NATIVE_BEHAVIOR_V1 {cid}":
            raise ValueError("case does not bind to one native prompt event")
        reads = sorted(e["observed_read_target"] for e in session if "observed_read_target" in e)
        if reads != case["observed_read_targets"]:
            raise ValueError("read observation mismatch")
        if cid == "manual-control":
            expected, targets = {markers["always.mdc"]}, []
        else:
            pred = predictions[cid]
            expected = {markers[PurePosixPath(r["file"]).name] for r in pred["acs_prediction"]["rules"]
                        if r["activation"] == "active"}
            targets = pred["targets"]
        results.append({"id": cid, "visible_marker_set_matches": visible == expected,
                        "unexpected_observed_reads": sorted(set(reads) - set(targets)),
                        "complete_transcript_retained": case["complete_transcript_retained"]})
    return {"status": "retained_evidence_verified", "native_cases": len(cases),
            "automatic_contexts": len(predictions),
            "automatic_visible_marker_set_matches": sum(r["visible_marker_set_matches"] for r in results
                                                       if r["id"] != "manual-control"),
            "case_results": results, "complete_attachment_fidelity": "unresolved",
            "independent_accuracy_established": False, "general_accuracy_percentage": None,
            "note": "Offline artifact verification and comparison of assistant-transcribed screenshots; no native rerun, OCR or independent reviewer."}


def verify(base: Path) -> dict:
    index = load(base / "evidence-index.json")
    if not index.get("files"):
        raise ValueError("nonempty integrity index required")
    for name, expected in index["files"].items():
        if hashlib.sha256(member(base, name).read_bytes()).hexdigest() != expected:
            raise ValueError("retained evidence fingerprint mismatch")
    prepared, observed = load(base / "prepared-inputs.json"), load(base / "observations.json")
    for name, expected in prepared["inputs_sha256"].items():
        if name == ".cursor/hooks.json" and prepared["local_hook_config_not_published"]:
            continue
        if hashlib.sha256(member(base / "fixture", name).read_bytes()).hexdigest() != expected:
            raise ValueError("captured fixture fingerprint mismatch")
    for case in observed["cases"]:
        member(base, case["screenshot"])
    events = [json.loads(line) for line in (base / "behavior-events.jsonl").read_text(encoding="utf-8").splitlines()]
    return assess(prepared, observed, events)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    args = parser.parse_args()
    try:
        result = verify(args.base)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"native evidence verification failed ({type(error).__name__})\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
