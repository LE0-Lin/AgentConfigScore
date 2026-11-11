#!/usr/bin/env python3
"""Explicit read-only GitHub collection for the registered maintainer path audit.

Never run the scanner, downloaded commands, a model or maintainer outreach.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from collect_review_candidates import github_json, privacy_exclusion
from run_pinned_tool_probe import verify_tree_objects


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "benchmarks/path-audit-v1"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw, usedforsecurity=False).hexdigest()


def decode(data: dict) -> bytes:
    if data.get("type") != "file" or data.get("encoding") != "base64":
        raise ValueError("expected a regular base64 file")
    raw = base64.b64decode(data["content"])
    if blob_sha(raw) != data["sha"]:
        raise ValueError("content disagrees with Git blob identity")
    raw.decode("utf-8")
    return raw


def candidates(text: str, suffixes: list[str]) -> list[dict]:
    # A separate deliberately small sampler, not the scanner's path recognizer.
    matches = []
    for match in re.finditer(r"(?<!`)`([^`\n]+)`(?!`)", text):
        matches.append((match.start(), match.group(1), "literal"))
    for match in re.finditer(r"\[[^\]\n]*\]\(([^\s()]+)\)", text):
        matches.append((match.start(), match.group(1), "markdown_link"))
    result, seen = [], set()
    for offset, token, kind in sorted(matches):
        if (token in seen or not re.fullmatch(r"[A-Za-z0-9_./-]+", token)
                or token.startswith("/") or ".." in PurePosixPath(token).parts
                or not ("/" in token or PurePosixPath(token).suffix in suffixes)
                or re.match(r"(?:https?|git|ssh):", token)):
            continue
        seen.add(token)
        result.append({"line": text.count("\n", 0, offset) + 1,
                       "destination": token, "kind": kind})
    return result


def collect(repository: str, protocol: dict) -> tuple[dict, list[tuple[str, bytes]]]:
    row = {"repository": repository}

    def excluded(reason):
        return {**row, "status": "excluded", "reason": reason}, []

    meta = github_json(f"repos/{repository}")
    if meta is None or meta.get("private") is not False:
        return excluded("public_repository_unavailable")
    commit = github_json(f"repos/{repository}/commits/{meta['default_branch']}")
    row["revision"] = revision = commit["sha"]
    source = None
    row["source_checks"] = []
    for name in protocol["source_paths"]:
        source = github_json(f"repos/{repository}/contents/{name}?ref={revision}")
        row["source_checks"].append({"path": name, "present": source is not None})
        if source is not None:
            break
    if source is None:
        return excluded("registered_root_instruction_absent")
    if source.get("type") != "file":
        return excluded("instruction_not_regular_file")
    if source.get("size", 0) > protocol["maximum_source_bytes"]:
        return excluded("instruction_size_limit")
    license_data = github_json(f"repos/{repository}/license?ref={revision}")
    if license_data is None:
        return excluded("license_unavailable")
    row["license_spdx"] = license_data.get("license", {}).get("spdx_id")
    if row["license_spdx"] not in protocol["allowed_licenses"]:
        return excluded("license_outside_allowlist")
    raw, license_raw = decode(source), decode(license_data)
    if len(raw) > protocol["maximum_source_bytes"]:
        return excluded("instruction_size_limit")
    text = raw.decode("utf-8")
    if privacy_exclusion(text):
        return excluded("credential_shaped_privacy_exclusion")
    tree_sha = commit["commit"]["tree"]["sha"]
    tree = github_json(f"repos/{repository}/git/trees/{tree_sha}?recursive=1")
    if tree.get("truncated") is not False:
        return excluded("incomplete_recursive_tree")
    if len(tree["tree"]) > protocol["maximum_tree_entries"]:
        return excluded("tree_entry_limit")
    verify_tree_objects(tree, tree_sha)
    index = {entry["path"]: entry for entry in tree["tree"]}
    if index[source["path"]]["sha"] != source["sha"]:
        raise ValueError("instruction blob disagrees with canonical tree")
    name = repository.replace("/", "--")
    source_path = f"sources/{name}.txt"
    tree_path = f"trees/{name}.json.gz"
    license_path = f"licenses/{name}.txt"
    tree_raw = gzip.compress(json.dumps(tree, sort_keys=True, separators=(",", ":")).encode(), mtime=0)
    row.update({
        "status": "collected", "instruction_path": source["path"],
        "source_file": source_path, "source_sha256": digest(raw), "source_blob_sha": source["sha"],
        "source_url": f"https://github.com/{repository}/blob/{revision}/{source['path']}",
        "tree_file": tree_path, "tree_sha256": digest(tree_raw), "tree_object_sha": tree_sha,
        "tree_entries": len(tree["tree"]), "license_file": license_path,
        "license_sha256": digest(license_raw), "license_blob_sha": license_data["sha"],
        "license_url": f"https://github.com/{repository}/blob/{revision}/{license_data['path']}",
        "candidates": candidates(text, protocol["candidate_suffixes"]),
    })
    return row, [(source_path, raw), (tree_path, tree_raw), (license_path, license_raw)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=BASE / "protocol.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("collection requires a new directory")
    protocol_raw = args.protocol.read_bytes()
    protocol = json.loads(protocol_raw)
    rows, artifacts, selected = [], [], 0
    # Read-only repository acquisitions are independent. Registry order is retained.
    with ThreadPoolExecutor(max_workers=3) as executor:
        for row, files in executor.map(lambda repo: collect(repo, protocol), protocol["repositories"]):
            for index, candidate in enumerate(row.get("candidates", [])):
                candidate["selected"] = index < protocol["per_repository"] and selected < protocol["target_cases"]
                if candidate["selected"]:
                    selected += 1
                    candidate["id"] = f"path-{selected:02}"
            rows.append(row)
            artifacts.extend(files)
            print(f"{row['repository']}: {row['status']} ({len(row.get('candidates', []))} candidates)", flush=True)
    result = {"schema_version": 1, "status": "collected_unscored",
              "collected_at_utc": datetime.now(timezone.utc).isoformat(),
              "protocol_sha256": digest(protocol_raw), "selected_cases": selected,
              "repositories": rows}
    # Acquisition errors propagate before a completed collection is written.
    args.output_dir.mkdir(parents=True)
    artifacts.append(("collection.json", (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode()))
    for name, raw in artifacts:
        path = args.output_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            output.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
