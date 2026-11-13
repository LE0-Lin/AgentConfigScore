"""Offline installed-tool replay: known path fixes and a separate fresh registry.

Names-only Git projections; never execute or build upstream code. This is
development evidence, with no independent labels or external user feedback.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import run_path_audit as audit
from run_pinned_tool_probe import verify_tree_objects

ROOT = Path(__file__).resolve().parents[1]
FRESH = ROOT / "benchmarks/path-check-v2"


def fresh_inputs(base=FRESH):
    protocol = audit.json_file(base / "protocol.json")
    collection = audit.json_file(base / "collected/collection.json")
    if collection["protocol_sha256"] != audit.digest((base / "protocol.json").read_bytes()):
        raise ValueError("fresh protocol hash changed after collection")
    trees = {}
    for row in collection["repositories"]:
        if row["status"] != "collected":
            continue
        for path_key, sha_key in (("source_file", "source_sha256"), ("tree_file", "tree_sha256"),
                                  ("license_file", "license_sha256")):
            raw = (base / "collected" / audit.portable(row[path_key])).read_bytes()
            if audit.digest(raw) != row[sha_key]:
                raise ValueError("fresh retained source hash mismatch")
        tree = json.loads(gzip.decompress((base / "collected" / row["tree_file"]).read_bytes()))
        if tree.get("truncated") is not False or len(tree["tree"]) > protocol["maximum_tree_entries"]:
            raise ValueError("fresh complete bounded tree required")
        verify_tree_objects(tree, row["tree_object_sha"])
        source = (base / "collected" / row["source_file"]).read_bytes()
        index = {entry["path"]: entry for entry in tree["tree"]}
        if (audit.blob_sha(source) != row["source_blob_sha"]
                or index[row["instruction_path"]]["sha"] != row["source_blob_sha"]):
            raise ValueError("fresh source Git identity mismatch")
        trees[row["repository"]] = tree
    return protocol, collection, trees


def check(python: Path):
    _, _, collection, labels, trees = audit.verify_inputs(audit.BASE)
    frozen = audit.json_file(audit.BASE / "result.json")
    fresh_protocol, fresh_collection, fresh_trees = fresh_inputs()
    expected_identity = fresh_protocol["tool_source_sha256"]
    identity = None

    def scan(repo, tree, base, omitted=None):
        nonlocal identity
        data = audit.scan(python, tree, repo, base, omitted)
        tool = data["tool"]
        if (tool["source_fingerprint"]["sha256"] is None
                or (identity is not None and tool != identity)):
            raise ValueError("missing or mixed installed parser identity")
        identity = tool
        return data

    repos = {row["repository"]: row for row in collection["repositories"] if row["status"] == "collected"}
    natural, snapshots = [], {}
    for name, repo in repos.items():
        rows = [row for row in repo["candidates"] if row["selected"]]
        if not rows:
            continue
        result = scan(repo, trees[name], audit.BASE)
        snapshots[name] = result
        for row in rows:
            natural.append({"id": row["id"], "repository": name, "line": row["line"],
                            "destination": row["destination"], "provisional_review_needed": labels[row["id"]]["review_needed"],
                            "current_flagged": audit.flagged(result["findings"], row)})
        print("Known source replayed: " + name, flush=True)

    controls, explicit_variants = [], []
    for row in frozen["controls"]:
        name = row["repository"]
        result = scan(repos[name], trees[name], audit.BASE, row["target"])
        controls.append({key: row[key] for key in ("id", "repository", "target", "target_kind", "line", "destination")}
                        | {"frozen_flagged": row["tool_flagged"], "current_flagged": audit.flagged(result["findings"], row),
                           "current_findings": result["findings"], "projection": result["projection"]})
        print("Known control replayed: " + row["id"], flush=True)
        if row["target_kind"] == "tree" and row["destination"].endswith("/"):
            repo = repos[name]
            source = (audit.BASE / "collected" / repo["source_file"]).read_bytes()
            lines = source.decode("utf-8").splitlines(keepends=True)
            literal = "`" + row["destination"] + "`"
            if lines[row["line"] - 1].count(literal) != 1:
                raise ValueError("explicit-path variant needs one exact literal on the original line")
            destination = "./" + row["destination"]
            lines[row["line"] - 1] = lines[row["line"] - 1].replace(literal, "`" + destination + "`", 1)
            variant = "".join(lines).encode("utf-8")
            with TemporaryDirectory(prefix="acs-explicit-path-variant-") as directory:
                base = Path(directory)
                (base / "collected").mkdir()
                (base / "collected/variant.txt").write_bytes(variant)
                changed = scan({**repo, "source_file": "variant.txt"}, trees[name], base, row["target"])
            explicit_variants.append({"parent_control": row["id"], "repository": name,
                                      "line": row["line"], "original_destination": row["destination"],
                                      "destination": destination, "source_sha256": audit.digest(source),
                                      "variant_source_sha256": audit.digest(variant),
                                      "synthetic_instruction_edit": "prefix ./ to the one quoted directory on this line",
                                      "target_removed": row["target"],
                                      "current_flagged": audit.flagged(changed["findings"], {**row, "destination": destination}),
                                      "findings": changed["findings"]})

    context = audit.json_file(audit.BASE / "posthoc-context.json")
    vitest_tree = {entry["path"]: entry for entry in trees["vitest-dev/vitest"]["tree"]}
    for row in context["files"]:
        raw = row["content"].encode("utf-8")
        if audit.digest(raw) != row["sha256"] or audit.blob_sha(raw) != vitest_tree[row["path"]]["sha"]:
            raise ValueError("retained generator source evidence mismatch")
    generated_case = {"line": 201, "destination": "docs/.vitepress/contributor-names.json"}
    old = frozen["whole_document_path_findings_unscored_outside_selected_cases"]["vitest-dev/vitest"]["findings"]
    generated = {**generated_case, "repository": "vitest-dev/vitest", "source_revision": context["revision"],
                 "frozen_flagged": audit.flagged(old, generated_case),
                 "current_flagged": audit.flagged(snapshots["vitest-dev/vitest"]["findings"], generated_case),
                 "producer_context_git_verified": True}

    fresh = []
    for repo in fresh_collection["repositories"]:
        if repo["status"] != "collected":
            fresh.append({"repository": repo["repository"], "status": "excluded", "reason": repo["reason"]})
            continue
        tree = fresh_trees[repo["repository"]]
        result = scan(repo, tree, FRESH)
        selected = [row for row in repo["candidates"] if row["selected"]]
        index = {entry["path"] for entry in tree["tree"]}
        fresh.append({"repository": repo["repository"], "revision": repo["revision"],
                      "status": "completed_source_smoke", "selected_candidates": len(selected),
                      "source_url": repo["source_url"], "findings": result["findings"],
                      "candidates": [{**row, "literal_tracked_name_present": row["destination"].rstrip("/").removeprefix("./") in index,
                                      "tool_flagged": audit.flagged(result["findings"], row), "reference_label": None}
                                     for row in selected], "projection": result["projection"]})
        print("Fresh source replayed: " + repo["repository"], flush=True)
    previous_snapshots = frozen["whole_document_path_findings_unscored_outside_selected_cases"]
    new_warnings = []
    for name, result in snapshots.items():
        previous = {(row["line"], row["message"]) for row in previous_snapshots[name]["findings"]}
        new_warnings.extend({"repository": name, **row} for row in result["findings"]
                            if (row["line"], row["message"]) not in previous)
    return {"schema_version": 1, "status": "completed_development_replay",
            "completed_at_utc": datetime.now(timezone.utc).isoformat(), "tool": identity,
            "frozen_tool": frozen["tool"], "independent_accuracy_estimate": None,
            "external_user_feedback": None, "source_projection": "Git-verified names, empty non-instruction files",
            "source_freeze_commit": "4b8ebc0", "fresh_protocol_sha256": fresh_collection["protocol_sha256"],
            "fresh_parser_matches_collection_freeze": identity["source_fingerprint"]["sha256"] == expected_identity,
            "frozen_result_sha256": audit.digest((audit.BASE / "result.json").read_bytes()),
            "runner_sha256_lf": hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode()).hexdigest(),
            "known_natural_cases": natural, "known_controls": controls, "explicit_directory_variants": explicit_variants,
            "known_generated_output": generated,
            "known_whole_document_observations": snapshots, "new_whole_document_warnings": new_warnings,
            "fresh_registry": fresh}


def acceptance(data):
    """Known development contracts only; never score fresh unresolved inputs."""
    failures = []
    generated = data["known_generated_output"]
    if generated["current_flagged"]:
        failures.append("known_generated_output_warning_returned")
    for row in data["known_controls"]:
        explicit_directory = row["destination"].startswith(("./", "../")) and row["destination"].endswith("/")
        if (row["target_kind"] == "blob" or explicit_directory) and not row["current_flagged"]:
            failures.append("required_control_missed:" + row["id"])
    for row in data["explicit_directory_variants"]:
        if not row["current_flagged"]:
            failures.append("explicit_directory_variant_missed:" + row["parent_control"])
    for row in data["known_natural_cases"]:
        if row["current_flagged"] and row["provisional_review_needed"] is False:
            failures.append("known_natural_negative_flagged:" + row["id"])
    for row in data["new_whole_document_warnings"]:
        # A new finding on these already reviewed documents requires explicit
        # maintenance review, even when it is outside the selected 16 cases.
        failures.append(f"new_unreviewed_path_warning:{row['repository']}:{row['line']}")
    return {"passed": not failures, "scope": "known_development_contracts_only", "failures": failures}


def markdown(data):
    rows = data["known_controls"]
    lines = ["# Path-reference development replay", "", "Known development inputs; no independent accuracy estimate or external user adoption claim.", "",
             "| Known control | Literal | Frozen 0.26.1 | Current source |", "|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['id']} | `{row['destination']}` | {row['frozen_flagged']} | {row['current_flagged']} |")
    generated = data["known_generated_output"]
    lines += ["", f"Vitest's declared generated output: frozen warning **{generated['frozen_flagged']}**, current warning **{generated['current_flagged']}**.",
              "Producer source was checked against the retained Git tree. Upstream code was never built or executed.", "",
              f"Known target-removal controls detected: {sum(r['frozen_flagged'] for r in rows)}/{len(rows)} frozen; {sum(r['current_flagged'] for r in rows)}/{len(rows)} current.",
              "Unprefixed directory names remain outside the default prose heuristic. These mutations are not natural upstream defects.", "",
              "## Separate explicit-directory variants", "",
              f"Detected {sum(r['current_flagged'] for r in data['explicit_directory_variants'])}/{len(data['explicit_directory_variants'])} synthetic variants after prefixing ./ to the selected literal, then removing its target.",
              "Both the instruction spelling and target state change in these separate controls. They are not pooled with unchanged-text controls.", "",
              "## Separate fresh registry", "", "| Repository | Result | Selected candidates |", "|---|---|---|"]
    for row in data["fresh_registry"]:
        lines.append(f"| {row['repository']} | {row.get('reason', row['status'])} | {row.get('selected_candidates', 0)} |")
    lines += ["", "The fixed fresh registry produced no eligible path candidates. It supplies no fresh correctness estimate; exclusions were not replaced.",
              "The collected document's raw scanner observations remain in JSON, without human reference labels.", "",
              "## Reproduction identity", "", f"Current source: `{data['tool']['source_fingerprint']['sha256']}`.",
              f"Frozen published source: `{data['frozen_tool']['source_fingerprint']['sha256']}`.",
              "The changed implementation is an unreleased source build even when its package version string still says 0.26.1.", ""]
    lines += [f"Parser matches the pre-collection freeze: {data['fresh_parser_matches_collection_freeze']}.",
              "A later parser may replay these inputs as development data; a mismatch does not preserve first-use freshness.",
              f"Known development acceptance passed: {data['acceptance']['passed']}.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, required=True)
    args = parser.parse_args(argv)
    if os.name == "nt":
        parser.error("Use a case-sensitive Linux filesystem for the complete tracked-name projections")
    if args.output.exists() or args.markdown.exists():
        parser.error("Both report outputs must be new files")
    try:
        data = check(args.python.absolute())
        data["acceptance"] = acceptance(data)
        with args.output.open("x", encoding="utf-8") as out:
            out.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        with args.markdown.open("x", encoding="utf-8") as out:
            out.write(markdown(data))
        print(json.dumps({"known_development_acceptance": data["acceptance"]}), flush=True)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"Path replay failed ({type(error).__name__}); partial outputs are not completed evidence.\n")
    return 0 if data["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
