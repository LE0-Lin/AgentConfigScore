#!/usr/bin/env python3
"""Collect pinned tree facts and bounded referenced documents, never predictions."""
from __future__ import annotations

import argparse
import base64
from collections import deque
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
from urllib.parse import unquote

from collect_review_candidates import github_json, privacy_exclusion
from run_review_comparison import _digest, _fixture_path, _write_outputs, load_corpus, validate_corpus


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "benchmarks" / "prospective-review-v1"
LINK = re.compile(r"\[[^\]\n]+\]\(<?([^\s)>]+)>?\)")
TICK = re.compile(r"`([^`\n]+)`")
BARE = re.compile(r"(?<![\w/])(?:\.\.?/|[\w.-]+/)*[\w.-]+\.(?:md|rst|txt|toml|ya?ml|json|py|rs|tsx?|sh)\b")


def local_references(text: str) -> list[tuple[str, int]]:
    urls = [match.span() for match in re.finditer(r"https?://[^\s)>]+", text)]
    found = set()
    for pattern in (LINK, TICK, BARE):
        for match in pattern.finditer(text):
            value = match.group(1) if pattern is not BARE else match.group(0)
            if (value.startswith("#") or re.match(r"[a-zA-Z][\w+.-]*:", value)
                    or any(start <= match.start() < end for start, end in urls)
                    or any(char.isspace() for char in value)):
                continue
            if pattern is TICK and "/" not in value and not PurePosixPath(value).suffix:
                continue
            found.add((value, text.count("\n", 0, match.start()) + 1))
    return sorted(found, key=lambda row: (row[1], row[0]))


def relative_target(source: str, reference: str) -> str | None:
    value = unquote(reference.split("#", 1)[0].split("?", 1)[0])
    if not value or value.startswith("/"):
        return None
    target = posixpath.normpath(posixpath.join(posixpath.dirname(source), value))
    if target == ".":
        return target
    try:
        _fixture_path(target)
    except ValueError:
        return None
    return target


class GitEvidence:
    def __init__(self, repository: str, revision: str, protocol: dict):
        self.repository, self.revision, self.protocol = repository, revision, protocol
        data = github_json(f"repos/{repository}/git/trees/{revision}?recursive=1")
        if (not isinstance(data, dict) or data.get("truncated") is not False
                or not isinstance(data.get("tree"), list)
                or len(data["tree"]) > protocol["maximum_tree_entries"]):
            raise ValueError("a complete, bounded Git tree is required; no case was dropped")
        self.snapshot = {"sha": data["sha"], "truncated": False, "tree": sorted(data["tree"], key=lambda row: row["path"])}
        self.index = {row["path"]: row for row in data["tree"]}
        if len(self.index) != len(data["tree"]):
            raise ValueError("duplicate Git tree paths")
        self.blobs: dict[str, bytes] = {}

    def blob(self, sha: str) -> bytes:
        if sha not in self.blobs:
            data = github_json(f"repos/{self.repository}/git/blobs/{sha}")
            if not isinstance(data, dict) or data.get("encoding") != "base64" or data.get("sha") != sha:
                raise ValueError("pinned Git blob could not be retrieved")
            raw = base64.b64decode(data["content"])
            identity = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw, usedforsecurity=False).hexdigest()
            if identity != sha:
                raise ValueError("Git blob identity mismatch")
            self.blobs[sha] = raw
        return self.blobs[sha]

    def resolve(self, path: str) -> tuple[str, str]:
        if path == ".":
            return path, "tracked_directory"
        visited = set()
        for _ in range(self.protocol["maximum_symlink_hops"] + 1):
            if path in visited:
                return path, "symlink_cycle"
            visited.add(path)
            parts = path.split("/")
            redirected = False
            for number in range(1, len(parts) + 1):
                prefix = "/".join(parts[:number])
                entry = self.index.get(prefix)
                if entry is None:
                    return path, "not_in_tracked_tree"
                if entry["mode"] == "160000" and number < len(parts):
                    return path, "inside_gitlink_unknown"
                if entry["mode"] == "120000":
                    raw = self.blob(entry["sha"])
                    if len(raw) > 4096:
                        return path, "unsupported_symlink"
                    try:
                        target = relative_target(prefix, raw.decode("utf-8"))
                    except UnicodeError:
                        return path, "unsupported_symlink"
                    if target is None:
                        return path, "outside_or_nonportable_path"
                    suffix = "/".join(parts[number:])
                    path = posixpath.join(target, suffix) if suffix else target
                    redirected = True
                    break
            if not redirected:
                entry = self.index[path]
                return path, {"blob": "tracked_file", "tree": "tracked_directory", "commit": "gitlink"}.get(entry["type"], "unknown_type")
        return path, "symlink_hop_limit"


def collect_case(original: dict, protocol: dict) -> tuple[dict, dict, bytes]:
    source = original["provenance"]
    evidence = GitEvidence(source["repository"], source["revision"], protocol)
    origin, status = evidence.resolve(source["path"])
    if status != "tracked_file":
        raise ValueError("root instruction origin is unresolved; retain the case and investigate")
    root_raw = evidence.blob(evidence.index[origin]["sha"])
    if hashlib.sha256(root_raw).hexdigest() != source["source_sha256"]:
        raise ValueError("pinned root content differs from the parent candidate; collection stopped")
    case = copy.deepcopy(original)
    files = case["files"]
    facts, omissions, documents = [], [], []
    origins = {source["path"]: origin}
    seen = {origin}
    queue = deque([(source["path"], origin, root_raw.decode("utf-8"), 0)])
    total_bytes = 0
    while queue:
        supplied_path, actual_path, text, depth = queue.popleft()
        requested = set()
        for reference, line in local_references(text):
            target = relative_target(actual_path, reference)
            resolved, state = evidence.resolve(target) if target else ("", "outside_or_nonportable_path")
            root_target = relative_target("AGENTS.md", reference)
            root_path, root_state = evidence.resolve(root_target) if root_target else ("", "outside_or_nonportable_path")
            if len(facts) < protocol["maximum_reference_facts_per_case"]:
                facts.append({"file": supplied_path, "line": line, "reference": reference,
                              "resolved_path": resolved, "tree_status": state,
                              "root_relative_path": root_path, "root_tree_status": root_state})
            else:
                omissions.append({"path": reference, "reason": "reference_fact_limit"})
            if state == "tracked_file" and PurePosixPath(resolved).suffix.lower() in protocol["document_extensions"]:
                requested.add(resolved)
            if root_state == "tracked_file" and PurePosixPath(root_path).suffix.lower() in protocol["document_extensions"]:
                requested.add(root_path)
        for target in sorted(requested):
            if target in seen:
                continue
            seen.add(target)
            reason = None
            if depth >= protocol["maximum_document_depth"]:
                reason = "document_depth_limit"
            elif len(documents) >= protocol["maximum_documents_per_case"]:
                reason = "document_count_limit"
            entry = evidence.index[target]
            if entry.get("size", 0) > protocol["maximum_document_bytes"]:
                reason = "document_byte_limit"
            if reason:
                omissions.append({"path": target, "reason": reason})
                continue
            try:
                _fixture_path(target)
                raw = evidence.blob(entry["sha"])
                content = raw.decode("utf-8")
            except UnicodeError:
                omissions.append({"path": target, "reason": "non_utf8_document"})
                continue
            except ValueError as exc:
                if "fixture paths" not in str(exc):
                    raise
                omissions.append({"path": target, "reason": "nonportable_document_path"})
                continue
            if len(raw) > protocol["maximum_document_bytes"]:
                reason = "document_byte_limit"
            elif total_bytes + len(raw) > protocol["maximum_context_bytes_per_case"]:
                reason = "context_byte_limit"
            elif privacy_exclusion(content):
                reason = "credential_shaped_document_privacy_exclusion"
            if reason:
                omissions.append({"path": target, "reason": reason})
                continue
            if target in files:
                raise ValueError("context document collides with an existing supplied path")
            files[target] = content
            origins[target] = target
            total_bytes += len(raw)
            documents.append({"path": target, "blob_sha": entry["sha"], "source_sha256": hashlib.sha256(raw).hexdigest(),
                              "source_url": f"https://github.com/{source['repository']}/blob/{source['revision']}/{target}",
                              "line_start": 1, "line_end": len(content.splitlines())})
            queue.append((target, target, content, depth + 1))
    archive_name = f"trees/{original['id']}.json.gz"
    archive = gzip.compress(json.dumps(evidence.snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8"), mtime=0)
    case["repository_context"] = {"content_origins": origins, "tracked_path_facts": facts, "omitted_documents": omissions}
    case["context_provenance"] = {
        "tree_archive": archive_name, "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "tree_snapshot_sha256": _digest(evidence.snapshot), "tree_object_sha": evidence.snapshot["sha"],
        "tree_entries": len(evidence.index), "tree_truncated": False, "documents": documents,
    }
    case["rationale"] = "Unreviewed candidate with bounded pinned context; no human reference label or system prediction."
    audit = {"id": case["id"], "root_source_path": origin, "tree_entries": len(evidence.index),
             "additional_documents": len(documents), "additional_bytes": total_bytes,
             "reference_facts": len(facts), "omissions": omissions}
    return case, audit, archive


def validate_protocol(protocol: dict) -> None:
    if not isinstance(protocol, dict) or type(protocol.get("schema_version")) is not int or protocol["schema_version"] != 1:
        raise ValueError("context protocol schema_version must be 1")
    for field in ("maximum_tree_entries", "maximum_documents_per_case", "maximum_document_bytes",
                  "maximum_context_bytes_per_case", "maximum_document_depth", "maximum_symlink_hops",
                  "maximum_reference_facts_per_case"):
        if type(protocol.get(field)) is not int or protocol[field] <= 0:
            raise ValueError("context collection limits must be positive integers")
    if protocol.get("document_extensions") != [".md", ".rst", ".txt"]:
        raise ValueError("context collection supports only the registered text-document extension set")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=BASE / "collected" / "corpus.json")
    parser.add_argument("--protocol", type=Path, default=BASE / "context-protocol.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output_dir.exists():
            raise ValueError("context collection requires a new output directory")
        original = load_corpus(args.corpus)
        protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
        validate_protocol(protocol)
        if (original["tier"] != "candidate" or original["labelers"]
                or _digest(original) != protocol["input_corpus_sha256"]
                or original["scanner_revision"] != protocol["scanner_revision"]):
            raise ValueError("context protocol must match the exact unreviewed parent collection")
        corpus = copy.deepcopy(original)
        corpus.update(name=protocol["name"], parent_corpus_sha256=_digest(original),
                      context_protocol_sha256=_digest(protocol))
        corpus["sampling_note"] += " Bounded shared context is collected under a separate frozen protocol."
        cases, rows, archives = [], [], []
        for case in original["cases"]:
            enriched, audit, archive = collect_case(case, protocol)
            cases.append(enriched)
            rows.append(audit)
            archives.append((args.output_dir / enriched["context_provenance"]["tree_archive"], archive))
            print(f"{case['id']}: {audit['additional_documents']} documents; {audit['reference_facts']} facts; {len(audit['omissions'])} omissions", flush=True)
        corpus["cases"] = cases
        validate_corpus(corpus)
        report = {"schema_version": 1, "collected_at_utc": datetime.now(timezone.utc).isoformat(),
                  "status": "unreviewed_context_only", "parent_corpus_sha256": _digest(original),
                  "corpus_sha256": _digest(corpus), "protocol_sha256": _digest(protocol), "cases": rows}
        encode = lambda value: json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        notices = []
        for case in original["cases"]:
            name = case["provenance"]["license_notice"]
            notices.append((args.output_dir / _fixture_path(name), (args.corpus.parent / _fixture_path(name)).read_bytes()))
        _write_outputs([(args.output_dir / "corpus.json", encode(corpus)),
                        (args.output_dir / "collection.json", encode(report)),
                        (args.output_dir / "protocol.json", encode(protocol)), *notices, *archives])
        print("Retained all cases and unresolved labels. No scanner/model run or human annotation was performed.")
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
