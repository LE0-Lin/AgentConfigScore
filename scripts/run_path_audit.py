#!/usr/bin/env python3
"""Offline replay of a bounded, provisional maintainer path audit.

The child reads the pinned installed library, not this checkout's runtime.
Only selected root instruction bytes and a names-only projection are supplied.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import subprocess
import tempfile

from collect_path_audit import blob_sha, digest
from run_pinned_tool_probe import verify_tree_objects


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "benchmarks/path-audit-v1"
REFERENCE_COMMIT = "aa5e4c75e2257513601626e891aa217044e771d7"
EXPECTED_SOURCE_SHA256 = "d6b3b079d6a8ab0d870020abe5f6489b59536c5a6602e2083dfc80b0c97d1ed5"
WORKER = r'''
import json, sys
from pathlib import Path
from unittest.mock import patch
from agent_config_score import scanner
from agent_config_score.provenance import capture_tool_identity
root = Path(sys.argv[1]).resolve()
source = root / sys.argv[2]
# Explicit research scope. No policy, suppressions, candidate-parser patch or
# root discovery equivalence is claimed. The full selected text is unchanged.
with patch.object(scanner, "discover", return_value=[source]):
    report = scanner.analyze(root).to_dict()
print(json.dumps({"tool": capture_tool_identity().to_dict(), "findings": [
    {key: row[key] for key in ("file", "line", "message")}
    for row in report["findings"] if row["code"] == "dead-path"
]}))
'''


def json_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_inputs(base: Path) -> tuple[dict, dict, dict, dict, dict]:
    protocol = json_file(base / "protocol.json")
    controls = json_file(base / "control-protocol.json")
    collection = json_file(base / "collected/collection.json")
    observations = json_file(base / "observations.json")
    if digest((base / "protocol.json").read_bytes()) != collection["protocol_sha256"]:
        raise ValueError("protocol fingerprint mismatch")
    trees = {}
    selected = []
    for repo in collection["repositories"]:
        if repo["status"] != "collected":
            continue
        for field, sha_field in (("source_file", "source_sha256"), ("tree_file", "tree_sha256"),
                                 ("license_file", "license_sha256")):
            path = portable(repo[field])
            raw = (base / "collected" / path).read_bytes()
            if digest(raw) != repo[sha_field]:
                raise ValueError("retained artifact fingerprint mismatch")
        raw = (base / "collected" / repo["source_file"]).read_bytes()
        if blob_sha(raw) != repo["source_blob_sha"]:
            raise ValueError("instruction Git blob mismatch")
        tree = json.loads(gzip.decompress((base / "collected" / repo["tree_file"]).read_bytes()))
        if tree.get("truncated") is not False or len(tree["tree"]) > protocol["maximum_tree_entries"]:
            raise ValueError("complete bounded tree required")
        verify_tree_objects(tree, repo["tree_object_sha"])
        index = {entry["path"]: entry for entry in tree["tree"]}
        if index[repo["instruction_path"]]["sha"] != repo["source_blob_sha"]:
            raise ValueError("source does not match pinned tree")
        trees[repo["repository"]] = tree
        selected.extend(case["id"] for case in repo["candidates"] if case["selected"])
    labels = {case["id"]: case for case in observations["cases"]}
    if (len(labels) != len(observations["cases"]) or set(labels) != set(selected)
            or len(selected) != collection["selected_cases"]
            or any(type(case["review_needed"]) not in (bool, type(None)) for case in labels.values())):
        raise ValueError("one provisional observation per selected case is required")
    return protocol, controls, collection, labels, trees


def portable(name: str) -> str:
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name
            or ":" in name or any(part.casefold() == ".git" for part in path.parts)):
        raise ValueError("unsafe projection path")
    return path.as_posix()


def projection(root: Path, tree: dict, source_name: str, source: bytes, omitted: str | None) -> dict:
    skipped = []
    for row in tree["tree"]:
        name = portable(row["path"])
        if omitted and (name == omitted or name.startswith(omitted + "/")):
            continue
        if row["mode"] == "120000" or row["type"] == "commit":
            skipped.append(name)
            continue
        target = root / name
        if row["type"] == "tree":
            target.mkdir(parents=True, exist_ok=True)
        elif row["mode"] in {"100644", "100755"} and row["type"] == "blob":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch(exist_ok=False)
        else:
            raise ValueError("unsupported tree entry")
    (root / source_name).write_bytes(source)
    return {"omitted_target": omitted, "skipped_aliases_or_gitlinks": skipped,
            "non_instruction_file_contents": "empty placeholders, not upstream contents"}


def scan(python: Path, tree: dict, repo: dict, base: Path, omitted: str | None = None) -> dict:
    with tempfile.TemporaryDirectory(prefix="acs-path-audit-") as directory:
        root = Path(directory)
        evidence = projection(root, tree, repo["instruction_path"],
                              (base / "collected" / repo["source_file"]).read_bytes(), omitted)
        env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
        result = subprocess.run([str(python), "-I", "-X", "utf8", "-c", WORKER,
                                 str(root), repo["instruction_path"]], cwd=root, env=env,
                                capture_output=True, encoding="utf-8", timeout=180)
        if result.returncode:
            raise ValueError("installed library audit failed; no completed report")
        return {**json.loads(result.stdout), "projection": evidence}


def flagged(findings: list[dict], case: dict) -> bool:
    return any(row["line"] == case["line"]
               and row["message"] == "Referenced path does not exist: " + case["destination"]
               for row in findings)


def counts(cases: list[dict]) -> dict:
    result = {"cases": len(cases), "true_positive": 0, "false_positive": 0,
              "true_negative": 0, "false_negative": 0, "unresolved": 0}
    for row in cases:
        expected, actual = row["review_needed"], row["tool_flagged"]
        key = ("unresolved" if expected is None else
               "true_positive" if expected and actual else
               "false_negative" if expected else
               "false_positive" if actual else "true_negative")
        result[key] += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True, help="Installed v0.26.1 Python")
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.name == "nt":
        parser.error("use a case-sensitive Linux filesystem for the tracked-name projection")
    if args.output.exists():
        parser.error("output must be new; retained runs are never overwritten")
    base = args.base.resolve()
    protocol, controls, collection, labels, trees = verify_inputs(base)
    natural, mutations, scans, seen_targets = [], [], {}, set()
    identity = None
    for repo in collection["repositories"]:
        cases = [case for case in repo.get("candidates", []) if case["selected"]]
        if not cases:
            continue
        tree = trees[repo["repository"]]
        index = {row["path"]: row for row in tree["tree"]}
        report = scan(args.python.resolve(), tree, repo, base)
        if (report["tool"]["version"] != protocol["product_version"]
                or report["tool"]["source_fingerprint"]["sha256"] != EXPECTED_SOURCE_SHA256):
            raise ValueError("audit requires the frozen published package and source identity")
        if identity is not None and identity != report["tool"]:
            raise ValueError("tool changed during audit")
        identity = report["tool"]
        scans[repo["repository"]] = report
        for case in cases:
            row = {**case, "repository": repo["repository"], "source_url": repo["source_url"],
                   "review_needed": labels[case["id"]]["review_needed"],
                   "reason": labels[case["id"]]["reason"],
                   "tool_flagged": flagged(report["findings"], case)}
            natural.append(row)
            target = posixpath.normpath(case["destination"])
            key = (repo["repository"], target)
            entry = index.get(target)
            if (len(mutations) >= controls["cases"] or key in seen_targets or entry is None
                    or entry["mode"] not in {"040000", "100644", "100755"}):
                continue
            seen_targets.add(key)
            mutated = scan(args.python.resolve(), tree, repo, base, target)
            if mutated["tool"] != identity:
                raise ValueError("tool changed during control")
            mutations.append({"id": f"control-{len(mutations) + 1:02}", "parent_case": case["id"],
                              "repository": repo["repository"], "target": target,
                              "target_kind": entry["type"], "line": case["line"],
                              "destination": case["destination"], "review_needed": True,
                              "tool_flagged": flagged(mutated["findings"], case),
                              "findings": mutated["findings"], "projection": mutated["projection"]})
        print(f"Replayed {repo['repository']} (selected natural cases: {len(cases)})", flush=True)
    if len(mutations) != controls["cases"]:
        raise ValueError("registered control count could not be completed")
    fingerprints = {name: digest((base / name).read_bytes()) for name in
                    ("protocol.json", "control-protocol.json", "observations.json", "collected/collection.json")}
    output = {"schema_version": 1, "status": "completed_provisional_maintainer_audit",
              "completed_at_utc": datetime.now(timezone.utc).isoformat(), "host": os.name,
              "reference_freeze_commit": REFERENCE_COMMIT, "input_sha256": fingerprints,
              "runner_sha256": digest(Path(__file__).read_bytes()), "tool": identity,
              "native_cursor_observed": False, "independent_human_labels": False,
              "natural_summary": counts(natural), "control_summary": counts(mutations),
              "accuracy_percentage": None, "natural_cases": natural, "controls": mutations,
              "whole_document_path_findings_unscored_outside_selected_cases": scans}
    with args.output.open("x", encoding="utf-8") as destination:
        json.dump(output, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
