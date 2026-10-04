#!/usr/bin/env python3
"""Explicitly fetch public GitHub candidates with gh; never run lint or labels.

This research helper uses the caller's existing GitHub CLI authentication.
It never executes downloaded instructions or submits reviews to maintainers.
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

from agent_config_score.rules import PATTERN_RULES
from run_review_comparison import _digest, _fixture_path, _write_outputs, validate_corpus


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = ROOT / "benchmarks" / "prospective-review-v1" / "protocol.json"
QUOTED_SECRET = re.compile(
    r"\b(?:password|api_key|access_token|auth_token|client_secret)\b\s*[:=]\s*['\"]([^'\"\r\n]+)['\"]",
    re.I,
)
PLACEHOLDERS = {"", "changeme", "example", "placeholder", "your-key", "your-token", "your-password"}


def privacy_exclusion(text: str) -> bool:
    if any(rule.pattern.search(text) for rule in PATTERN_RULES if rule.rule.category == "secret"):
        return True
    return any(match.group(1).casefold() not in PLACEHOLDERS for match in QUOTED_SECRET.finditer(text))


def github_json(endpoint: str) -> dict | None:
    result = subprocess.run(["gh", "api", endpoint], capture_output=True, timeout=45)
    if result.returncode:
        # Missing files are declared exclusions. Transport/auth errors are not
        # quietly turned into missing files, nor copied into a public artifact.
        try:
            error = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            error = {}
        if error.get("status") in (404, "404") or b"(HTTP 404)" in result.stderr:
            return None
        raise ValueError("GitHub API failed; no completed collection was written")
    return json.loads(result.stdout)


def decoded_file(data: dict) -> tuple[bytes, str]:
    if data.get("type") != "file" or data.get("encoding") != "base64":
        raise ValueError("GitHub returned a non-file or unsupported encoding")
    raw = base64.b64decode(data["content"], validate=False)
    return raw, raw.decode("utf-8")


def validate_protocol(protocol: dict) -> None:
    if (not isinstance(protocol, dict) or type(protocol.get("schema_version")) is not int
            or protocol.get("schema_version") != 1
            or not isinstance(protocol.get("scanner_revision"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", protocol["scanner_revision"])):
        raise ValueError("protocol needs version 1 and a pinned scanner revision")
    _fixture_path(protocol["source_path"])
    if type(protocol.get("maximum_source_bytes")) is not int or protocol["maximum_source_bytes"] <= 0:
        raise ValueError("protocol needs a positive source-byte limit")
    if (not isinstance(protocol.get("allowed_licenses"), list) or not protocol["allowed_licenses"]
            or not all(isinstance(value, str) and value for value in protocol["allowed_licenses"])):
        raise ValueError("declare allowed licenses")
    rows = protocol.get("repositories")
    if not isinstance(rows, list) or not rows:
        raise ValueError("protocol needs a fixed repository registry")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("registry entries must be objects")
        name = row.get("repository", "")
        component = r"[A-Za-z0-9][A-Za-z0-9_.-]*"
        if (not isinstance(name, str) or not re.fullmatch(f"{component}/{component}", name)
                or not isinstance(row.get("group"), str) or not row["group"].strip() or name.casefold() in seen):
            raise ValueError("registry repositories must be valid, unique, and grouped")
        seen.add(name.casefold())


def collect_one(row: dict, protocol: dict) -> tuple[dict, dict | None, tuple[str, str] | None]:
    name = row["repository"]
    audit = {"repository": name, "group": row["group"]}

    def excluded(reason):
        return {**audit, "status": "excluded", "reason": reason}, None, None

    metadata = github_json(f"repos/{name}")
    if metadata is None:
        return excluded("repository_unavailable")
    if metadata.get("private") is not False:
        return excluded("not_a_public_repository")
    commit = github_json(f"repos/{name}/commits/{quote(metadata['default_branch'], safe='')}")
    if commit is None or not re.fullmatch(r"[0-9a-f]{40}", commit.get("sha", "")):
        raise ValueError("could not pin a repository revision")
    sha = commit["sha"]
    audit["revision"] = sha
    data = github_json(f"repos/{name}/contents/{quote(protocol['source_path'], safe='/')}?ref={sha}")
    if data is None:
        return excluded("root_instruction_file_absent")
    if data.get("type") != "file":
        return excluded("instruction_path_is_not_a_regular_file")
    if type(data.get("size")) is not int or data["size"] > protocol["maximum_source_bytes"]:
        return excluded("instruction_file_exceeds_size_limit")
    license_data = github_json(f"repos/{name}/license?ref={sha}")
    if license_data is None:
        return excluded("root_license_unavailable")
    spdx = license_data.get("license", {}).get("spdx_id")
    audit["license_spdx"] = spdx
    if spdx not in protocol["allowed_licenses"]:
        return excluded("license_not_in_registered_allowlist")
    try:
        raw, content = decoded_file(data)
        license_raw, license_text = decoded_file(license_data)
    except (ValueError, UnicodeError):
        return excluded("file_or_license_not_supported_utf8_text")
    if len(raw) > protocol["maximum_source_bytes"]:
        return excluded("instruction_file_exceeds_size_limit")
    if not content.strip():
        return excluded("empty_instruction_file")
    if privacy_exclusion(content):
        return excluded("credential_shaped_content_privacy_exclusion")
    source_url = f"https://github.com/{name}/blob/{sha}/{protocol['source_path']}"
    license_url = f"https://github.com/{name}/blob/{sha}/{license_data['path']}"
    license_output = f"licenses/{name.replace('/', '--')}.txt"
    case_id = name.replace("/", "--")
    lines = len(content.splitlines())
    source = {
        "repository": name, "revision": sha, "path": protocol["source_path"],
        "line_start": 1, "line_end": lines, "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_url": source_url, "license_spdx": spdx, "license_url": license_url,
        "license_notice": license_output, "license_sha256": hashlib.sha256(license_raw).hexdigest(),
    }
    case = {
        "id": case_id, "label": "unresolved", "category": "not_yet_annotated", "group": row["group"],
        "rationale": "No human reference annotation has been completed. Repository context has not been collected.",
        "source_kind": "repository_snapshot", "source_ref": source_url, "provenance": source,
        "files": {protocol["source_path"]: content},
    }
    return {**audit, "status": "included", "case_id": case_id, **source}, case, (license_output, license_text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output_dir.exists():
            raise ValueError("collection requires a new directory; existing evidence is never overwritten")
        protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
        validate_protocol(protocol)
        cases, audit, notices = [], [], []
        # Parallel read-only requests; output and case order remain registered order.
        with ThreadPoolExecutor(max_workers=3) as executor:
            for row, case, notice in executor.map(lambda value: collect_one(value, protocol), protocol["repositories"]):
                audit.append(row)
                print(f"{row['repository']}: {row['status']}", flush=True)
                if case is not None:
                    cases.append(case)
                    notices.append(notice)
        if not cases:
            raise ValueError("no eligible cases; retain the fixed registry and revise the protocol transparently")
        corpus = {
            "schema_version": 1, "name": protocol["name"], "tier": "candidate",
            "used_for_rule_development": False, "label_status": "unreviewed", "labelers": [],
            "sampling_note": protocol["selection"] + " " + protocol["context_boundary"],
            "protocol_sha256": _digest(protocol), "scanner_revision": protocol["scanner_revision"], "cases": cases,
        }
        report = {
            "schema_version": 1, "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            "protocol_sha256": _digest(protocol), "corpus_sha256": _digest(corpus),
            "included": len(cases), "excluded": len(audit) - len(cases),
            "status": "unreviewed_candidates_only", "repositories": audit,
        }
        validate_corpus(corpus)
        encode = lambda value: json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        _write_outputs([
            (args.output_dir / "corpus.json", encode(corpus)),
            (args.output_dir / "collection.json", encode(report)),
            (args.output_dir / "protocol.json", encode(protocol)),
            *[(args.output_dir / name, content) for name, content in notices],
        ])
        print(f"Collected {len(cases)} unresolved cases; no scanner/model run or human annotation was performed.")
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
