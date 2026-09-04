#!/usr/bin/env python3
"""Run the offline labeled AgentConfigScore mutation benchmark."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path, PurePosixPath
import tempfile
from typing import Any

from agent_config_score import __version__
from agent_config_score.regression import compare
from agent_config_score.rules import RULES_BY_CODE
from agent_config_score.scanner import analyze


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "benchmarks" / "adversarial_cases.json"


def _safe_relative_path(value: str) -> Path:
    pure = PurePosixPath(value)
    if not value or "\\" in value or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"benchmark file path must stay inside its fixture: {value!r}")
    return Path(*pure.parts)


def _write_files(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        target = root / _safe_relative_path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _codes_for_scan(files: dict[str, str]) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="acs-adversarial-scan-") as directory:
        root = Path(directory)
        _write_files(root, files)
        return sorted({finding.code for finding in analyze(root).findings})


def _codes_for_regression(base_files: dict[str, str], head_files: dict[str, str]) -> list[str]:
    with (
        tempfile.TemporaryDirectory(prefix="acs-adversarial-base-") as base_directory,
        tempfile.TemporaryDirectory(prefix="acs-adversarial-head-") as head_directory,
    ):
        base = Path(base_directory)
        head = Path(head_directory)
        _write_files(base, base_files)
        _write_files(head, head_files)
        return sorted({finding.code for finding in compare(base, head).new_findings})


def _expand_contract_cases(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for template in corpus["scan_templates"]:
        for variant in corpus["file_variants"]:
            files = {
                (variant["path"] if rel == "{instruction}" else rel): content
                for rel, content in template["files"].items()
            }
            cases.append(
                {
                    "id": f"{template['id']}--{variant['id']}",
                    "mode": "scan",
                    "category": template["category"],
                    "note": template["note"],
                    "files": files,
                    "expected_codes": template["expected_codes"],
                }
            )
    for case in corpus["scan_cases"]:
        cases.append({"mode": "scan", **case})
    for case in corpus["regression_cases"]:
        cases.append({"mode": "regression", **case})
    return cases


def _validate_corpus(corpus: dict[str, Any], contract_cases: list[dict[str, Any]]) -> None:
    if corpus.get("schema_version") != 1:
        raise ValueError("adversarial corpus schema_version must be 1")
    ids = [case["id"] for case in contract_cases]
    challenge_ids = [case["id"] for case in corpus["challenge_cases"]]
    if len(ids) != len(set(ids)) or len(challenge_ids) != len(set(challenge_ids)):
        raise ValueError("benchmark case IDs must be unique within each tier")
    if set(ids) & set(challenge_ids):
        raise ValueError("contract and challenge case IDs must not overlap")
    for case in contract_cases:
        unknown = set(case["expected_codes"]) - RULES_BY_CODE.keys()
        if unknown:
            raise ValueError(f"{case['id']} references unknown rule IDs: {sorted(unknown)}")
        if not case["note"].strip():
            raise ValueError(f"{case['id']} must include a review note")
    for case in corpus["challenge_cases"]:
        if case.get("expected_detection") is not True:
            raise ValueError(f"{case['id']} must explicitly set expected_detection to true")
        if not case["note"].strip():
            raise ValueError(f"{case['id']} must include a review note")


def _observe(case: dict[str, Any]) -> list[str]:
    if case["mode"] == "scan":
        return _codes_for_scan(case["files"])
    if case["mode"] == "regression":
        return _codes_for_regression(case["base_files"], case["head_files"])
    raise ValueError(f"unknown benchmark mode for {case['id']}: {case['mode']!r}")


def _evaluate_contract(case: dict[str, Any]) -> dict[str, Any]:
    expected = sorted(set(case["expected_codes"]))
    observed = _observe(case)
    expected_set = set(expected)
    observed_set = set(observed)
    return {
        "id": case["id"],
        "mode": case["mode"],
        "category": case["category"],
        "expected_codes": expected,
        "observed_codes": observed,
        "missing_codes": sorted(expected_set - observed_set),
        "unexpected_codes": sorted(observed_set - expected_set),
        "exact_match": expected == observed,
        "note": case["note"],
    }


def _evaluate_challenge(case: dict[str, Any]) -> dict[str, Any]:
    observed = _observe(case)
    return {
        "id": case["id"],
        "mode": case["mode"],
        "category": case["category"],
        "expected_detection": True,
        "detected": bool(observed),
        "observed_codes": observed,
        "note": case["note"],
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _contract_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    true_positives = sum(len(set(row["expected_codes"]) & set(row["observed_codes"])) for row in rows)
    false_negatives = sum(len(row["missing_codes"]) for row in rows)
    false_positives = sum(len(row["unexpected_codes"]) for row in rows)
    precision = _ratio(true_positives, true_positives + false_positives)
    recall = _ratio(true_positives, true_positives + false_negatives)
    f1 = None
    if precision is not None and recall is not None and precision + recall:
        f1 = round(2 * precision * recall / (precision + recall), 4)
    clean = [row for row in rows if not row["expected_codes"]]
    return {
        "cases": len(rows),
        "exact_matches": sum(row["exact_match"] for row in rows),
        "case_accuracy": _ratio(sum(row["exact_match"] for row in rows), len(rows)),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "clean_cases": len(clean),
        "clean_cases_passed": sum(row["exact_match"] for row in clean),
    }


def _category_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["category"]].append(row)
    return [
        {
            "category": category,
            "cases": len(category_rows),
            "exact_matches": sum(row["exact_match"] for row in category_rows),
            "accuracy": _ratio(sum(row["exact_match"] for row in category_rows), len(category_rows)),
        }
        for category, category_rows in sorted(grouped.items())
    ]


def evaluate(corpus_path: Path) -> dict[str, Any]:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    contract_cases = _expand_contract_cases(corpus)
    _validate_corpus(corpus, contract_cases)
    contract_rows = [_evaluate_contract(case) for case in contract_cases]
    challenge_rows = [_evaluate_challenge(case) for case in corpus["challenge_cases"]]
    contract_summary = _contract_summary(contract_rows)
    detected_challenges = sum(row["detected"] for row in challenge_rows)
    return {
        "schema_version": 1,
        "agent_config_score_version": __version__,
        "corpus": str(corpus_path),
        "all_contracts_matched": contract_summary["exact_matches"] == contract_summary["cases"],
        "contract_summary": contract_summary,
        "category_summary": _category_summary(contract_rows),
        "challenge_summary": {
            "cases": len(challenge_rows),
            "detected": detected_challenges,
            "missed": len(challenge_rows) - detected_challenges,
            "detection_rate": _ratio(detected_challenges, len(challenge_rows)),
            "gating": False,
        },
        "contract_cases": contract_rows,
        "challenge_cases": challenge_rows,
    }


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def markdown_report(result: dict[str, Any]) -> str:
    summary = result["contract_summary"]
    challenge = result["challenge_summary"]
    lines = [
        "# AgentConfigScore Benchmark v1",
        "",
        f"Deterministic contract cases: **{summary['exact_matches']}/{summary['cases']} exact matches**.",
        "",
        f"- Precision: **{_percent(summary['precision'])}**",
        f"- Recall: **{_percent(summary['recall'])}**",
        f"- F1: **{_percent(summary['f1'])}**",
        f"- Clean negative controls: **{summary['clean_cases_passed']}/{summary['clean_cases']} passed**",
        "",
        "| Category | Exact matches | Accuracy |",
        "|---|---:|---:|",
    ]
    for row in result["category_summary"]:
        lines.append(
            f"| `{row['category']}` | {row['exact_matches']}/{row['cases']} | {_percent(row['accuracy'])} |"
        )
    lines.extend(
        [
            "",
            "## Open challenge set",
            "",
            f"Detected **{challenge['detected']}/{challenge['cases']}** labeled challenges. "
            "Challenge results are reported but do not control the benchmark exit code.",
            "",
            "| Challenge | Category | Detected | Observed rules |",
            "|---|---|---:|---|",
        ]
    )
    for row in result["challenge_cases"]:
        codes = ", ".join(f"`{code}`" for code in row["observed_codes"]) or "—"
        lines.append(
            f"| `{row['id']}` | `{row['category']}` | {'yes' if row['detected'] else 'no'} | {codes} |"
        )
    lines.extend(
        [
            "",
            "The contract tier measures behavior the deterministic scanner currently promises. "
            "The challenge tier keeps known semantic and rule-surface misses visible instead of inflating the headline metric.",
            "",
        ]
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, help="Write the complete JSON result")
    parser.add_argument("--markdown", type=Path, help="Write a compact Markdown report")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = evaluate(args.corpus.resolve())
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.output}")
    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown_report(result), encoding="utf-8")
        print(f"wrote {args.markdown}")
    return 0 if result["all_contracts_matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
