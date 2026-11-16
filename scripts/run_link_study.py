#!/usr/bin/env python3
"""Collect, then replay the registered narrow CommonMark target-existence study.

No upstream code, instructions, build, model, or outreach is executed. Study-only
dependencies belong in an isolated environment; ACS runtime remains dependency-free.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
from importlib.metadata import version
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import sys
from urllib.parse import quote, unquote, urlsplit

from markdown_it import MarkdownIt

from collect_path_audit import blob_sha, decode, digest
from collect_review_candidates import github_json, privacy_exclusion
from run_path_audit import portable, scan
from run_pinned_tool_probe import verify_tree_objects


BASE = Path(__file__).resolve().parents[1] / "benchmarks/link-existence-v1"


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(raw)


def parser_identity() -> dict:
    identity = {name: version(name) for name in ("markdown-it-py", "mdurl")}
    if identity != {"markdown-it-py": "3.0.0", "mdurl": "0.1.2"}:
        raise ValueError("use the frozen study requirements")
    return identity


def document_names(tree: dict, limit: int) -> list[str]:
    regular = {row["path"] for row in tree["tree"]
               if row["type"] == "blob" and row["mode"] in {"100644", "100755"}}
    priority = ["AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md"]
    rest = sorted(name for name in regular - set(priority)
                  if PurePosixPath(name).name in {"AGENTS.md", "CLAUDE.md"})
    return ([name for name in priority if name in regular] + rest)[:limit]


def local_target(href: str, source: str, index: dict) -> dict:
    """Independent reference: CommonMark href + lexical Git path lookup only."""
    try:
        parts = urlsplit(href)
    except ValueError:
        return {"excluded": "invalid_url"}
    if parts.scheme or parts.netloc or not parts.path:
        return {"excluded": "external_or_anchor_only"}
    destination = unquote(parts.path)
    if destination.startswith("/") or not re.fullmatch(r"[A-Za-z0-9_./+@ -]+", destination):
        return {"excluded": "absolute_or_nonportable_destination"}
    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), destination))
    if target == ".." or target.startswith("../"):
        return {"excluded": "out_of_root"}
    # ACS also tries a repository-root fallback. Neither resolution may rely on
    # an alias that our names-only projection cannot faithfully materialize.
    for candidate in (target, posixpath.normpath(destination)):
        path = PurePosixPath(candidate)
        for parent in (path, *path.parents):
            entry = index.get(parent.as_posix())
            if entry and (entry["mode"] == "120000" or entry["type"] == "commit"):
                return {"excluded": "symlink_or_gitlink_dependency"}
    entry = index.get(target)
    exists = target == "." or bool(entry and (entry["type"] == "tree" or
                                            entry["mode"] in {"100644", "100755"}))
    return {"destination": destination, "resolved_target": target, "target_exists": exists}


def reference_cases(text: str, source: str, tree: dict) -> tuple[list, list]:
    parser_identity()
    index = {row["path"]: row for row in tree["tree"]}
    tokens = MarkdownIt("commonmark").parse(text)
    candidates, exclusions, seen = [], [], set()
    lines = text.splitlines()
    for token in tokens:
        if token.type != "inline" or not token.map:
            continue
        for child in token.children or []:
            if child.type != "link_open":
                continue
            href = child.attrGet("href")
            row = {"href": href, "line": token.map[0] + 1,
                   "block_end_line": token.map[1]}
            if token.map[1] - token.map[0] != 1:
                exclusions.append({**row, "excluded": "multiline_inline_block"})
                continue
            fact = local_target(href, source, index)
            if "excluded" in fact:
                exclusions.append({**row, **fact})
                continue
            if fact["destination"] in seen:
                exclusions.append({**row, "excluded": "duplicate_document_destination"})
                continue
            seen.add(fact["destination"])
            candidates.append({**row, **fact, "source_line": lines[token.map[0]]})
    return candidates, exclusions


def acquire(repository: str, protocol: dict) -> tuple[dict, list]:
    row = {"repository": repository}

    def excluded(reason):
        return {**row, "status": "excluded", "reason": reason}, []

    metadata = github_json(f"repos/{repository}")
    if metadata is None or metadata.get("private") is not False:
        return excluded("public_repository_unavailable")
    commit = github_json(f"repos/{repository}/commits/{quote(metadata['default_branch'], safe='')}")
    row["revision"] = revision = commit["sha"]
    row["tree_object_sha"] = tree_sha = commit["commit"]["tree"]["sha"]
    tree = github_json(f"repos/{repository}/git/trees/{tree_sha}?recursive=1")
    if tree.get("truncated") is not False:
        return excluded("incomplete_recursive_tree")
    if len(tree["tree"]) > protocol["maximum_tree_entries"]:
        return excluded("tree_entry_limit")
    verify_tree_objects(tree, tree_sha)
    try:
        for entry in tree["tree"]:
            portable(entry["path"])
    except ValueError:
        return excluded("unsupported_projection_path")
    names = document_names(tree, protocol["maximum_documents_per_repository"])
    row["selected_documents"] = names
    if not names:
        return excluded("no_registered_instruction_file")
    license_data = github_json(f"repos/{repository}/license?ref={revision}")
    if license_data is None:
        return excluded("license_unavailable")
    row["license_spdx"] = license_data.get("license", {}).get("spdx_id")
    if row["license_spdx"] not in protocol["allowed_licenses"]:
        return excluded("license_outside_allowlist")
    prefix = repository.replace("/", "--")
    license_raw = decode(license_data)
    tree_raw = gzip.compress(json.dumps(tree, sort_keys=True, separators=(",", ":")).encode(), mtime=0)
    row.update({"status": "collected", "tree_file": f"trees/{prefix}.json.gz",
                "tree_sha256": digest(tree_raw), "tree_entries": len(tree["tree"]),
                "license_file": f"licenses/{prefix}.txt", "license_sha256": digest(license_raw),
                "license_blob_sha": license_data["sha"],
                "license_url": f"https://github.com/{repository}/blob/{revision}/{license_data['path']}",
                "documents": []})
    artifacts = [(row["tree_file"], tree_raw), (row["license_file"], license_raw)]
    index = {entry["path"]: entry for entry in tree["tree"]}
    for number, name in enumerate(names):
        doc = {"instruction_path": name}
        row["documents"].append(doc)
        if index[name].get("size", 0) > protocol["maximum_source_bytes"]:
            doc.update(status="excluded", reason="source_size_limit")
            continue
        data = github_json(f"repos/{repository}/contents/{quote(name, safe='/')}?ref={revision}")
        if data["sha"] != index[name]["sha"]:
            raise ValueError("source disagrees with canonical tree")
        try:
            raw = decode(data)
        except UnicodeError:
            doc.update(status="excluded", reason="not_utf8")
            continue
        if len(raw) > protocol["maximum_source_bytes"] or privacy_exclusion(raw.decode("utf-8")):
            doc.update(status="excluded", reason="size_or_credential_shaped_privacy_exclusion")
            continue
        cases, exclusions = reference_cases(raw.decode("utf-8"), name, tree)
        doc.update(status="collected", source_file=f"sources/{prefix}-{number:02}.txt",
                   source_sha256=digest(raw), source_blob_sha=data["sha"],
                   source_url=f"https://github.com/{repository}/blob/{revision}/{name}",
                   candidates=cases, exclusions=exclusions)
        artifacts.append((doc["source_file"], raw))
    return row, artifacts


def collect(base: Path, output: Path) -> None:
    protocol_raw = (base / "protocol.json").read_bytes()
    protocol = json.loads(protocol_raw)
    rows, files, total = [], [], 0
    with ThreadPoolExecutor(max_workers=3) as pool:
        for row, artifacts in pool.map(lambda name: acquire(name, protocol), protocol["repositories"]):
            selected = 0
            for doc in row.get("documents", []):
                for case in doc.get("candidates", []):
                    case["selected"] = (selected < protocol["maximum_cases_per_repository"]
                                        and total < protocol["maximum_cases"])
                    if case["selected"]:
                        selected += 1
                        total += 1
                        case["id"] = f"link-{total:03}"
            rows.append(row)
            files.extend(artifacts)
            print(f"{row['repository']}: {row['status']}, {selected} selected", flush=True)
    record = {"schema_version": 1, "status": "reference_collected_before_scanner",
              "collected_at_utc": datetime.now(timezone.utc).isoformat(),
              "protocol_sha256": digest(protocol_raw), "parser": parser_identity(),
              "selected_cases": total, "repositories": rows}
    for name, raw in [*files, ("collection.json", encoded(record))]:
        write_new(output / name, raw)


def flagged(findings: list, destination: str) -> bool:
    return any(row["message"] == "Referenced path does not exist: " + destination for row in findings)


def counts(rows: list) -> dict:
    result = dict(cases=len(rows), TP=0, FP=0, TN=0, FN=0)
    for row in rows:
        expected, actual = not row["target_exists"], row["tool_flagged"]
        result["TP" if expected and actual else "FN" if expected else "FP" if actual else "TN"] += 1
    result["missing_target_recall"] = result["TP"] / (result["TP"] + result["FN"]) if result["TP"] + result["FN"] else None
    result["warning_precision"] = result["TP"] / (result["TP"] + result["FP"]) if result["TP"] + result["FP"] else None
    return result


def replay(base: Path, output: Path) -> None:
    if os.name == "nt":
        raise ValueError("replay requires a case-sensitive Linux filesystem")
    protocol = read_json(base / "protocol.json")
    collection = read_json(base / "collected/collection.json")
    if collection["protocol_sha256"] != digest((base / "protocol.json").read_bytes()):
        raise ValueError("protocol changed after acquisition")
    if collection["parser"] != parser_identity():
        raise ValueError("reference parser changed")
    natural, controls, scans, used = [], [], [], set()
    identity = None
    for repo in collection["repositories"]:
        if repo["status"] != "collected":
            continue
        for prefix in ("tree", "license"):
            raw = (base / "collected" / portable(repo[prefix + "_file"])).read_bytes()
            if digest(raw) != repo[prefix + "_sha256"]:
                raise ValueError("retained artifact changed")
        tree = json.loads(gzip.decompress((base / "collected" / repo["tree_file"]).read_bytes()))
        verify_tree_objects(tree, repo["tree_object_sha"])
        index = {entry["path"]: entry for entry in tree["tree"]}
        for doc in repo["documents"]:
            if doc["status"] != "collected":
                continue
            raw = (base / "collected" / portable(doc["source_file"])).read_bytes()
            if (digest(raw) != doc["source_sha256"] or blob_sha(raw) != doc["source_blob_sha"]
                    or index[doc["instruction_path"]]["sha"] != doc["source_blob_sha"]):
                raise ValueError("retained instruction changed")
            candidates, exclusions = reference_cases(raw.decode("utf-8"), doc["instruction_path"], tree)
            stripped = [{k: v for k, v in row.items() if k not in {"id", "selected"}} for row in doc["candidates"]]
            if candidates != stripped or exclusions != doc["exclusions"]:
                raise ValueError("independent reference extraction changed")
            selected = [case for case in doc["candidates"] if case["selected"]]
            if not selected:
                continue
            result = scan(Path(sys.executable).absolute(), tree, doc, base)
            if (result["tool"]["version"] != protocol["product_version"] or
                    result["tool"]["source_fingerprint"]["sha256"] != protocol["source_sha256"]):
                raise ValueError("use the unchanged published wheel")
            if identity is not None and identity != result["tool"]:
                raise ValueError("installed tool changed")
            identity = result["tool"]
            scans.append({"repository": repo["repository"], "instruction_path": doc["instruction_path"], **result})
            for case in selected:
                natural.append({**case, "repository": repo["repository"], "instruction_path": doc["instruction_path"],
                                "source_url": doc["source_url"], "tool_flagged": flagged(result["findings"], case["destination"])})
                target = case["resolved_target"]
                key = (repo["repository"], target)
                entry = index.get(target)
                if (len(controls) >= protocol["maximum_controls"] or not entry or key in used
                        or entry["mode"] not in {"100644", "100755"} or target == doc["instruction_path"]):
                    continue
                used.add(key)
                control = scan(Path(sys.executable).absolute(), tree, doc, base, target)
                if control["tool"] != identity:
                    raise ValueError("installed tool changed during control")
                controls.append({"parent_case": case["id"], "repository": repo["repository"],
                                 "removed_target": target, "destination": case["destination"],
                                 "target_exists": False, "tool_flagged": flagged(control["findings"], case["destination"]),
                                 "findings": control["findings"], "projection": control["projection"]})
            print(f"Replayed {repo['repository']} / {doc['instruction_path']}: {len(selected)} cases", flush=True)
    if len(natural) != collection["selected_cases"]:
        raise ValueError("selected case count changed")
    report = {"schema_version": 1, "status": "completed_objective_component_check",
              "completed_at_utc": datetime.now(timezone.utc).isoformat(),
              "protocol_sha256": collection["protocol_sha256"],
              "collection_sha256": digest((base / "collected/collection.json").read_bytes()),
              "parser": parser_identity(), "tool": identity, "host": sys.platform,
              "natural_summary": counts(natural), "control_summary": counts(controls),
              "control_shortfall": protocol["maximum_controls"] - len(controls),
              "natural_cases": natural, "removal_controls": controls, "scans": scans,
              "limitations": protocol["reporting"]}
    write_new(output, encoded(report))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("collect", "replay"))
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be new; retain prior attempts")
    (collect if args.action == "collect" else replay)(args.base.resolve(), args.output)


if __name__ == "__main__":
    main()
