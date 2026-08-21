from __future__ import annotations

from . import __version__
from .rules import get_rule
from .scanner import Finding, Report

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_VERSION = "2.1.0"


def _level(severity: str) -> str:
    return {"error": "error", "warning": "warning", "info": "note"}.get(severity, "none")


def _rule(finding: Finding) -> dict:
    metadata = get_rule(finding.code)
    severity = metadata.severity if metadata is not None else finding.severity
    summary = metadata.summary if metadata is not None else finding.message
    rule = {
        "id": finding.code,
        "name": finding.code,
        "shortDescription": {"text": summary},
        "defaultConfiguration": {"level": _level(severity)},
        "properties": {"tags": ["ai-agent", "configuration"]},
    }
    if metadata is not None:
        rule["fullDescription"] = {"text": metadata.description}
        rule["properties"].update({"category": metadata.category, "penalty": metadata.penalty})
    return rule


def _result(finding: Finding, rule_index: int) -> dict:
    result = {
        "ruleId": finding.code,
        "ruleIndex": rule_index,
        "level": _level(finding.severity),
        "message": {"text": finding.message},
        "properties": {"penalty": finding.penalty},
    }

    if finding.file != "(repo)":
        physical_location = {
            "artifactLocation": {"uri": finding.file},
        }
        if finding.line is not None:
            physical_location["region"] = {"startLine": finding.line}
        result["locations"] = [{"physicalLocation": physical_location}]

    return result


def sarif_report(report: Report) -> dict:
    rules_by_code: dict[str, Finding] = {}
    for finding in report.findings:
        rules_by_code.setdefault(finding.code, finding)

    rule_codes = sorted(rules_by_code)
    rule_indexes = {code: index for index, code in enumerate(rule_codes)}
    rules = [_rule(rules_by_code[code]) for code in rule_codes]
    results = [_result(finding, rule_indexes[finding.code]) for finding in report.findings]

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AgentConfigScore",
                        "semanticVersion": __version__,
                        "informationUri": "https://github.com/LE0-Lin/AgentConfigScore",
                        "rules": rules,
                    }
                },
                "results": results,
                "properties": {
                    "score": report.score,
                    "grade": report.grade,
                    "estimatedTokens": report.estimated_tokens,
                    "duplicateRatio": report.duplicate_ratio,
                },
            }
        ],
    }
