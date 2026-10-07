#!/usr/bin/env python3
"""Read one verified public source snapshot; retain unscored native/scoped lint.

Explicit network access downloads source data only. No repository command, hook,
dependency installer, model, human label, or maintainer message is executed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tarfile
import time
from unittest.mock import patch
from urllib.request import urlopen

from agent_config_score import __version__, scanner
from collect_review_candidates import github_json
from collect_review_context import GitEvidence, relative_target
from run_review_comparison import _digest, _fixture_path, _tool_fingerprint, _write_outputs, load_corpus, review_packet


BASE = Path(__file__).resolve().parents[1] / "benchmarks" / "prospective-review-v1"
PROBE_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode()).hexdigest()


def blob_identity(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw, usedforsecurity=False).hexdigest()


class ReadBudget:
    """Bound expanded data, including tar metadata, before parser allocations."""
    def __init__(self, source, maximum: int):
        self.source, self.maximum, self.total = source, maximum, 0

    def read(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("unbounded archive read is unsupported")
        raw = self.source.read(min(size, self.maximum - self.total + 1))
        self.total += len(raw)
        if self.total > self.maximum:
            raise ValueError("expanded archive resource limit exceeded")
        return raw


def inputs(corpus: dict, packet: dict, protocol: dict, context_dir: Path) -> tuple[dict, dict]:
    if (not isinstance(protocol, dict) or type(protocol.get("schema_version")) is not int
            or protocol["schema_version"] != 1):
        raise ValueError("tool probe protocol schema_version must be 1")
    for field in ("maximum_archive_bytes", "maximum_source_bytes", "maximum_file_bytes",
                  "maximum_tar_members", "maximum_symlink_hops", "maximum_download_seconds"):
        if type(protocol.get(field)) is not int or protocol[field] <= 0:
            raise ValueError("tool probe limits must be positive integers")
    if (corpus["tier"] != "candidate" or _digest(corpus) != protocol.get("context_corpus_sha256")
            or _tool_fingerprint() != protocol.get("tool_source_sha256")
            or corpus["scanner_revision"] != protocol.get("scanner_revision")):
        raise ValueError("tool probe must match the frozen unresolved corpus and tool source")
    selected = [row for row in corpus["cases"] if row["id"] == protocol.get("selected_case_id")]
    if len(selected) != 1:
        raise ValueError("the declared tool case must exist exactly once; no substitution")
    case = selected[0]
    if (review_packet({**corpus, "cases": [case]}) != packet
            or packet["packet_sha256"] != protocol.get("packet_sha256")):
        raise ValueError("the tool case must match the exact retained one-case packet")
    if protocol.get("instruction_files") != [case["provenance"]["path"]]:
        raise ValueError("this probe supports the declared root-instruction scope only")
    evidence = case["context_provenance"]
    raw = (context_dir / _fixture_path(evidence["tree_archive"])).read_bytes()
    if hashlib.sha256(raw).hexdigest() != evidence["archive_sha256"]:
        raise ValueError("retained tree archive fingerprint mismatch")
    tree = json.loads(gzip.decompress(raw))
    if (tree.get("truncated") is not False or _digest(tree) != evidence["tree_snapshot_sha256"]
            or tree.get("sha") != evidence["tree_object_sha"]
            or len(tree.get("tree", [])) != evidence["tree_entries"]):
        raise ValueError("a complete unchanged retained Git tree is required")
    validate_tree(tree, protocol)
    canonical = protocol.get("canonical_tree_object_sha", "")
    if not isinstance(canonical, str) or not re.fullmatch(r"[0-9a-f]{40}", canonical):
        raise ValueError("protocol needs the independently retrieved canonical tree identity")
    verify_tree_objects(tree, canonical)
    return case, tree


def validate_tree(tree: dict, protocol: dict) -> dict:
    index, folded = {}, set()
    for row in tree["tree"]:
        name = row["path"]
        _fixture_path(name)
        if any(part.casefold() == ".git" for part in Path(name).parts):
            raise ValueError("source snapshot cannot contain Git administration paths")
        if name.casefold() in folded:
            raise ValueError("tree paths collide on a case-insensitive filesystem")
        folded.add(name.casefold())
        index[name] = row
        if not re.fullmatch(r"[0-9a-f]{40}", row.get("sha", "")):
            raise ValueError("tree entry lacks a Git object identity")
        if (row.get("type"), row.get("mode")) not in {
            ("tree", "040000"), ("blob", "100644"), ("blob", "100755"), ("blob", "120000")
        }:
            raise ValueError("unsupported tree entry or gitlink; no partial-success scan")
        if row["type"] == "blob" and (
            type(row.get("size")) is not int or row["size"] < 0 or row["size"] > protocol["maximum_file_bytes"]
        ):
            raise ValueError("tree blob exceeds the registered file-byte limit")
    if (len(index) + 1 > protocol["maximum_tar_members"]
            or sum(row.get("size", 0) for row in index.values()) > protocol["maximum_source_bytes"]):
        raise ValueError("the complete tree exceeds the declared resource limits")
    for name in index:
        for parent in Path(name).parents:
            if parent.as_posix() != "." and index.get(parent.as_posix(), {}).get("type") != "tree":
                raise ValueError("every source parent must be a tracked directory")
    return index


def verify_tree_objects(tree: dict, expected_root: str) -> None:
    """Verify actual Git tree identities, not an API response's ref/alias SHA."""
    children = defaultdict(list)
    index = {row["path"]: row for row in tree["tree"]}
    for name, row in index.items():
        parent, basename = name.rsplit("/", 1) if "/" in name else ("", name)
        children[parent].append((basename.encode("utf-8"), row))
    for parent, rows in children.items():
        # Git sorts a directory as though '/' followed its basename. Mode text
        # in Git tree objects has no leading zero (040000 becomes 40000).
        ordered = sorted(rows, key=lambda item: item[0] + (b"/" if item[1]["type"] == "tree" else b""))
        raw = b"".join(row["mode"].lstrip("0").encode() + b" " + name + b"\0" + bytes.fromhex(row["sha"])
                       for name, row in ordered)
        actual = hashlib.sha1(f"tree {len(raw)}\0".encode() + raw, usedforsecurity=False).hexdigest()
        expected = index[parent]["sha"] if parent else expected_root
        if actual != expected:
            raise ValueError("recursive tree entries disagree with canonical Git tree objects")
    if "" not in children:
        raise ValueError("source snapshot has no root entries")


def download(repository: str, revision: str, destination: Path, protocol: dict) -> dict:
    component = r"[A-Za-z0-9][A-Za-z0-9_.-]*"
    if not re.fullmatch(f"{component}/{component}", repository) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("archive download requires a public repository name and exact commit")
    url = f"https://codeload.github.com/{repository}/tar.gz/{revision}"
    digest, size, started = hashlib.sha256(), 0, time.monotonic()
    # A failed download leaves an explicit .part artifact, never a success file.
    partial = destination.with_suffix(destination.suffix + ".part")
    if destination.exists() or partial.exists():
        raise ValueError("archive download requires new paths")
    with urlopen(url, timeout=45) as response, partial.open("xb") as output:
        if response.geturl() != url:
            raise ValueError("archive download unexpectedly redirected")
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > protocol["maximum_archive_bytes"] or time.monotonic() - started > protocol["maximum_download_seconds"]:
                raise ValueError("archive download exceeded the declared resource limits")
            digest.update(chunk)
            output.write(chunk)
    partial.rename(destination)
    return {"input_kind": "downloaded_by_probe", "source_url": url, "archive_sha256": digest.hexdigest(), "archive_bytes": size}


def local_archive(path: Path, protocol: dict) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError("local replay requires a regular archive file")
    size, digest = 0, hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            size += len(chunk)
            if size > protocol["maximum_archive_bytes"]:
                raise ValueError("local archive exceeds the declared resource limits")
            digest.update(chunk)
    return {"input_kind": "local_archive_replay", "archive_sha256": digest.hexdigest(), "archive_bytes": size,
            "transport_provenance": "not_authenticated_by_replay; pinned Git objects are verified independently"}


def unpack(archive_path: Path, root: Path, tree: dict, protocol: dict) -> dict:
    """Verify every Git blob, then create only real regular files/internal links.

    Never call extractall, preserve executable modes, or install Git metadata.
    On failure a partial data directory may remain, but no scan report is written.
    """
    index = validate_tree(tree, protocol)
    if root.exists() or root.is_symlink():
        raise ValueError("snapshot requires a new directory")
    root.mkdir(parents=True)
    root = root.resolve()
    seen, links, prefix, byte_count = set(), {}, None, 0
    # Include bounded header/padding overhead; compressed size alone does not
    # bound a gzip bomb or metadata consumed internally by the tar parser.
    maximum_expanded = protocol["maximum_source_bytes"] + protocol["maximum_tar_members"] * 2048 + 10240
    with gzip.open(archive_path, "rb") as source_archive, tarfile.open(
        fileobj=(expanded := ReadBudget(source_archive, maximum_expanded)), mode="r|"
    ) as archive:
        for count, member in enumerate(archive, 1):
            if count > protocol["maximum_tar_members"]:
                raise ValueError("archive member limit exceeded")
            name = member.name.rstrip("/")
            if prefix is None:
                _fixture_path(name)
                if "/" in name or not member.isdir() or member.size:
                    raise ValueError("archive must start with one root directory")
                prefix = name
                continue
            if not name.startswith(prefix + "/"):
                raise ValueError("archive member escaped its root")
            name = name[len(prefix) + 1:]
            _fixture_path(name)
            entry = index.get(name)
            if entry is None or name in seen:
                raise ValueError("unexpected or duplicate archive path")
            seen.add(name)
            path = root / _fixture_path(name)
            if member.isdir():
                if entry["type"] != "tree" or member.size:
                    raise ValueError("archive directory disagrees with Git tree")
                path.mkdir(parents=True, exist_ok=True)
                continue
            if entry["type"] != "blob" or member.issparse():
                raise ValueError("unsupported archive entry")
            if member.issym() and entry["mode"] == "120000":
                raw = member.linkname.encode("utf-8")
                if (member.size or len(raw) > 4096 or any(char in member.linkname for char in "\\?#%\x00\r\n")
                        or relative_target(name, member.linkname) is None):
                    raise ValueError("external or unsupported archive symlink")
                normal_seen = False
                for part in member.linkname.split("/"):
                    if part == ".." and normal_seen:
                        # Windows/POSIX may resolve 'alias/..' differently.
                        # Leading '../' is supported; do not certify a later
                        # parent traversal using lexical normalization alone.
                        raise ValueError("nonportable parent traversal in archive symlink")
                    if part not in ("", ".", ".."):
                        normal_seen = True
                links[name] = raw
            elif member.isfile() and entry["mode"] in ("100644", "100755"):
                if member.size != entry["size"] or member.size > protocol["maximum_file_bytes"]:
                    raise ValueError("archive file size disagrees with Git tree")
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("archive file data is absent")
                raw = source.read(member.size + 1)
            else:
                raise ValueError("archive type disagrees with Git tree; hardlinks/devices are not supported")
            byte_count += len(raw)
            if byte_count > protocol["maximum_source_bytes"]:
                raise ValueError("archive source-byte limit exceeded")
            if len(raw) != entry["size"] or blob_identity(raw) != entry["sha"]:
                raise ValueError("archive Git blob identity mismatch")
            if name not in links:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as output:
                    output.write(raw)
        # Consume the gzip trailer too: complete tar entries do not establish a
        # complete/CRC-valid transfer when the compressed stream was truncated.
        while expanded.read(65536):
            pass
    if seen != set(index):
        raise ValueError("archive omitted tracked entries; no partial-success scan")
    resolver = GitEvidence.__new__(GitEvidence)
    resolver.index, resolver.protocol = index, protocol
    resolver.blobs = {index[name]["sha"]: raw for name, raw in links.items()}
    for name, raw in links.items():
        target, state = resolver.resolve(name)
        if state not in ("tracked_file", "tracked_directory", "not_in_tracked_tree"):
            raise ValueError("unresolved symlink graph; no partial-success scan")
        path = root / _fixture_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Windows reparse points require native separators for relative targets.
        # Git blob identity above still verifies the original link bytes.
        os.symlink(raw.decode("utf-8").replace("/", os.sep), path, target_is_directory=state == "tracked_directory")
    # Check actual OS resolution too: lexical normalization alone cannot certify
    # a chain containing a directory link followed by '..'. No target is read.
    for name in links:
        try:
            (root / _fixture_path(name)).resolve(strict=False).relative_to(root)
        except (ValueError, RuntimeError) as exc:
            raise ValueError("OS symlink resolution escaped or cycled") from exc
    return {"status": "verified_tracked_source_snapshot", "retained_tree_response_sha": tree["sha"],
            "tree_snapshot_sha256": _digest(tree), "tree_entries": len(index),
            "regular_files": len(index) - len(links) - sum(row["type"] == "tree" for row in index.values()),
            "directories": sum(row["type"] == "tree" for row in index.values()),
            "symlinks": len(links), "verified_blob_bytes": byte_count,
            "symlink_materialization": "original relative targets with host-native separators",
            "git_metadata": "not_created", "executable_permissions": "not_preserved",
            "generated_ignored_untracked_files": "not_supplied"}


def verify_case(root: Path, case: dict) -> dict:
    root = root.resolve()
    origins = case["repository_context"]["content_origins"]
    for name, text in case["files"].items():
        path = root / _fixture_path(name)
        if path.resolve() != (root / _fixture_path(origins[name])).resolve():
            raise ValueError("supplied content origin disagrees with the physical snapshot")
        if path.read_bytes() != text.encode("utf-8"):
            raise ValueError("supplied instruction/context bytes changed")
    checked, unknown = 0, 0
    for fact in case["repository_context"]["tracked_path_facts"]:
        for path_field, state_field in (("resolved_path", "tree_status"), ("root_relative_path", "root_tree_status")):
            name, state = fact[path_field], fact[state_field]
            if state in ("tracked_file", "tracked_directory", "not_in_tracked_tree"):
                path = root if name == "." else root / _fixture_path(name)
                valid = (path.is_file() if state == "tracked_file" else path.is_dir()
                         if state == "tracked_directory" else not path.exists())
                if not valid:
                    raise ValueError("captured path fact disagrees with the physical snapshot")
                checked += 1
            else:
                unknown += 1
    return {"supplied_files_verified": len(case["files"]), "physical_path_facts_checked": checked,
            "unknown_path_facts_not_asserted": unknown}


def retained_report(report: scanner.Report) -> dict:
    # Fixed rule summaries prevent arbitrary input text or local paths from
    # leaking through a dynamic finding message. Raw report text is not printed.
    data = report.to_dict()
    data.pop("root")
    for finding in data["findings"]:
        finding["message"] = scanner.RULES_BY_CODE[finding["code"]].summary
    return {**data, "review_needed": bool(report.findings), "score_meaning": "lint heuristic, not correctness"}


def probe(root: Path, case: dict, protocol: dict) -> dict:
    before = verify_case(root, case)
    if (_tool_fingerprint() != protocol["tool_source_sha256"]
            or hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode()).hexdigest() != PROBE_SOURCE_SHA256):
        raise ValueError("tool source changed before scan")
    native = retained_report(scanner.analyze(root))
    scoped_paths = [root / _fixture_path(name) for name in protocol["instruction_files"]]
    # Research-only discovery control; scanner rules/path checks are unchanged.
    # This is NOT the installed CLI's default discovery behavior.
    with patch.object(scanner, "discover", return_value=scoped_paths):
        scoped = retained_report(scanner.analyze(root))
    if verify_case(root, case) != before:
        raise ValueError("supplied evidence changed during scan")
    if (_tool_fingerprint() != protocol["tool_source_sha256"]
            or hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode()).hexdigest() != PROBE_SOURCE_SHA256):
        raise ValueError("tool/probe source changed during scan")
    return {"input_verification": before, "native_discovery": native, "root_instruction_scope": scoped,
            "comparison_ready": False, "correctness_metrics": None, "human_reference_status": "unreviewed",
            "ai_status": "separate_existing_pilot_not_imported", "hybrid_status": "not_run",
            "remaining_parity_gaps": [
                "Native discovery may include instruction text not supplied to the AI packet.",
                "The root-scoped run controls discovery, but path checks use the full physical snapshot/index; the AI received bounded path facts only.",
                "Referenced documents are physically present; the scanner does not semantically review their text unless discovery selects them.",
                "No independent human reference annotation or matched comparative model batch exists."
            ]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=BASE / "tool-probe-protocol.json")
    parser.add_argument("--archive", type=Path, help="Replay a local archive offline; every pinned Git object is still verified")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output_dir.exists() or args.output_dir.is_symlink():
            raise ValueError("tool probe requires a new output directory")
        corpus = load_corpus(BASE / "context" / "corpus.json")
        packet = json.loads((BASE / "pilot" / "review-packet.json").read_text(encoding="utf-8"))
        protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
        case, tree = inputs(corpus, packet, protocol, BASE / "context")
        source = case["provenance"]
        canonical_tree = protocol["canonical_tree_object_sha"]
        if args.archive is None:
            commit = github_json(f"repos/{source['repository']}/commits/{source['revision']}")
            if (not commit or commit.get("sha") != source["revision"]
                    or commit.get("commit", {}).get("tree", {}).get("sha") != canonical_tree):
                raise ValueError("pinned commit does not match the registered canonical tree")
        args.output_dir.mkdir(parents=True)
        if args.archive is None:
            print("Downloading one pinned source archive as data; no source commands will run.", flush=True)
            archive_path = args.output_dir / "source.tar.gz"
            archive = download(source["repository"], source["revision"], archive_path, protocol)
        else:
            print("Verifying a local archive offline; no source commands will run.", flush=True)
            archive_path = args.archive
            archive = local_archive(archive_path, protocol)
        print("Verifying every tracked entry and blob before scanning.", flush=True)
        # Keep downloaded instructions out of a later scan of OUR workspace.
        # 'vendor' is already excluded by the unchanged native scanner when
        # scanning an ancestor; it is not part of paths relative to this root.
        root = args.output_dir / "vendor" / "source"
        snapshot = unpack(archive_path, root, tree, protocol)
        snapshot["canonical_tree_object_sha"] = canonical_tree
        result = probe(root, case, protocol)
        report = {"schema_version": 1, "status": "actual_tool_probe_unscored",
                  "completed_at_utc": datetime.now(timezone.utc).isoformat(), "selected_case_id": case["id"],
                  "repository": source["repository"], "source_revision": source["revision"],
                  "packet_sha256": packet["packet_sha256"], "context_corpus_sha256": _digest(corpus),
                  "protocol_sha256": _digest(protocol), "tool_source_sha256": _tool_fingerprint(),
                  "probe_source_sha256": PROBE_SOURCE_SHA256,
                  "package_version": __version__, "python_version": platform.python_version(),
                  "host_platform": platform.system(), "archive": archive, "snapshot": snapshot, **result}
        _write_outputs([(args.output_dir / "report.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n"),
                        (args.output_dir / "protocol.json", json.dumps(protocol, indent=2, ensure_ascii=False) + "\n")])
        print(f"Retained unscored tool evidence: native {len(result['native_discovery']['files'])} instruction files, root scope {len(result['root_instruction_scope']['files'])}. Correctness metrics remain null.")
    except (ValueError, OSError, EOFError, HTTPException, tarfile.TarError, subprocess.TimeoutExpired) as exc:
        # Do not print server responses, source text, archive link contents, or
        # credential-bearing exception messages. Partial data are not a run.
        parser.exit(2, f"tool probe failed ({type(exc).__name__}); no completed report. Check inputs, transport, and limits.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
