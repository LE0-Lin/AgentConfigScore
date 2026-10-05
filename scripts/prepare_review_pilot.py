#!/usr/bin/env python3
"""Prepare one bounded review packet under a declared protocol; no model call."""
import argparse
import copy
import json
from pathlib import Path
import re

from run_review_comparison import _digest, _write_outputs, load_corpus, predictions_template, review_packet


BASE = Path(__file__).resolve().parents[1] / "benchmarks" / "prospective-review-v1"


def prepare(corpus, protocol):
    if (not isinstance(protocol, dict) or type(protocol.get("schema_version")) is not int
            or protocol["schema_version"] != 1
            or not isinstance(protocol.get("context_corpus_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", protocol["context_corpus_sha256"])):
        raise ValueError("pilot protocol needs version 1 and an exact corpus fingerprint")
    for name in ("maximum_text_bytes", "maximum_packet_bytes"):
        if type(protocol.get(name)) is not int or protocol[name] <= 0:
            raise ValueError("pilot resource limits must be positive integer bytes")
    if corpus["tier"] != "candidate" or _digest(corpus) != protocol["context_corpus_sha256"]:
        raise ValueError("pilot must use the exact unresolved context corpus")
    considered = []
    for case in corpus["cases"]:
        text_bytes = sum(len(text.encode("utf-8")) for text in case["files"].values())
        subset = {**corpus, "cases": [case]}
        packet = review_packet(subset)
        encoded = json.dumps(packet, indent=2, ensure_ascii=False) + "\n"
        packet_bytes = len(encoded.encode("utf-8"))
        eligible = (bool(case["context_provenance"]["documents"])
                    and text_bytes <= protocol["maximum_text_bytes"]
                    and packet_bytes <= protocol["maximum_packet_bytes"])
        considered.append({"id": case["id"], "text_bytes": text_bytes, "packet_bytes": packet_bytes,
                           "eligible_under_resource_limits": eligible})
        if eligible:
            return copy.deepcopy(packet), {"status": "prepared_not_run", "selected_case_id": case["id"],
                                          "packet_sha256": packet["packet_sha256"], "considered": considered,
                                          "protocol_sha256": _digest(protocol), "corpus_sha256": _digest(corpus)}
    raise ValueError("no candidate meets the declared pilot resource limits; do not substitute after observing results")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output_dir.exists():
            raise ValueError("pilot preparation requires a new output directory")
        corpus = load_corpus(BASE / "context" / "corpus.json")
        protocol = json.loads((BASE / "pilot-protocol.json").read_text(encoding="utf-8"))
        packet, manifest = prepare(corpus, protocol)
        encode = lambda value: json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        _write_outputs([(args.output_dir / "review-packet.json", encode(packet)),
                        (args.output_dir / "predictions-template.json", encode(predictions_template(packet))),
                        (args.output_dir / "preparation.json", encode(manifest)),
                        (args.output_dir / "protocol.json", encode(protocol))])
        print(f"Prepared exactly one opaque case; packet bytes: {len(encode(packet).encode('utf-8'))}. No model was run.")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
