#!/usr/bin/env python3
"""Replay a local verified snapshot with current rules as DEVELOPMENT evidence.

Not the frozen tool probe, an independent holdout, or an accuracy comparison.
No download, foreign command, model run, human label or maintainer contact.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import tarfile

from agent_config_score import __version__
from run_pinned_tool_probe import BASE, inputs, local_archive, probe, unpack
from run_review_comparison import _digest, _tool_fingerprint, _write_outputs, load_corpus


def development_policy(frozen: dict) -> dict:
    # Only the product fingerprint is substituted for current-code verification.
    # Never rewrite the frozen protocol, its source identity, safety or limits.
    return {**frozen, "tool_source_sha256": _tool_fingerprint()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="Existing pinned source archive; no download")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory on a compatible filesystem")
    args = parser.parse_args()
    try:
        if args.output_dir.exists() or args.output_dir.is_symlink():
            raise ValueError("development check requires a new output directory")
        frozen = json.loads((BASE / "tool-probe" / "replay-protocol.json").read_text(encoding="utf-8"))
        reuse = json.loads((BASE / "development-reuse.json").read_text(encoding="utf-8"))
        if reuse["status"] != "development_reuse_not_independent_holdout":
            raise ValueError("explicit development reuse disclosure is required")
        policy = development_policy(frozen)
        corpus = load_corpus(BASE / "context" / "corpus.json")
        packet = json.loads((BASE / "pilot" / "review-packet.json").read_text(encoding="utf-8"))
        case, tree = inputs(corpus, packet, policy, BASE / "context")
        archive = local_archive(args.archive, policy)
        args.output_dir.mkdir(parents=True)
        root = args.output_dir / "vendor" / "source"
        print("Verifying local source data before current-rule development checks.", flush=True)
        snapshot = unpack(args.archive, root, tree, policy)
        snapshot["canonical_tree_object_sha"] = policy["canonical_tree_object_sha"]
        result = probe(root, case, policy)
        report = {
            "schema_version": 1, "status": "development_check_not_independent_evaluation",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "selected_case_id": case["id"], "repository": case["provenance"]["repository"],
            "source_revision": case["provenance"]["revision"],
            "development_change_base_revision": reuse["base_product_revision"],
            "product_state": "current source checkout, identified by tool fingerprint; package version alone does not identify rule state",
            "package_version": __version__, "python_version": platform.python_version(),
            "host_platform": platform.system(), "tool_source_sha256": _tool_fingerprint(),
            "development_script_sha256": hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode()).hexdigest(),
            "frozen_protocol_sha256": _digest(frozen), "development_policy_sha256": _digest(policy),
            "policy_derivation": "Same source, scopes and safety limits as frozen protocol; only tool_source_sha256 replaced for current rules in memory. No frozen artifact was rewritten.",
            "development_reuse_sha256": _digest(reuse), "context_corpus_sha256": _digest(corpus),
            "packet_sha256": packet["packet_sha256"], "archive": archive, "snapshot": snapshot,
            "used_for_rule_development": True, **result,
        }
        _write_outputs([(args.output_dir / "report.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")])
        print("Retained development-only observations. Independent accuracy and human labels remain unavailable.")
    except (ValueError, OSError, EOFError, tarfile.TarError) as exc:
        parser.exit(2, f"development check failed ({type(exc).__name__}); no completed report.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
