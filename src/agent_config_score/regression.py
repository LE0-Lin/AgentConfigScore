from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .config import Suppression
from .scanner import (
    Finding,
    Report,
    SuppressedFinding,
    _analyze_with_texts,
    _directives,
    _finding,
    _matching_suppression,
)


def _finding_key(finding: Finding) -> tuple[str, str, str, str]:
    # Line numbers are intentionally excluded so harmless line shifts do not
    # turn an existing finding into a fake regression.
    return (finding.severity, finding.code, finding.file, finding.message)


def _regression_findings(base_texts: dict[str, str], head_texts: dict[str, str]) -> list[Finding]:
    # Only newly added files in the same directory may count as exact-text moves.
    # Consume each target once: an existing copy or one new file cannot hide
    # multiple deletions. Preserve literal whitespace; scan reads normalize EOLs.
    moved_contents = Counter(
        (PurePosixPath(rel).parent, head_texts[rel])
        for rel in head_texts.keys() - base_texts.keys()
        if head_texts[rel].strip()
    )
    findings: list[Finding] = []

    for rel in sorted(set(base_texts) - set(head_texts)):
        key = (PurePosixPath(rel).parent, base_texts[rel])
        if moved_contents[key] > 0:
            moved_contents[key] -= 1
            continue
        findings.append(
            _finding(
                "instruction-file-removed",
                rel,
                message=f"Supported instruction file was removed: {rel}",
            )
        )

    def directive_index(texts: dict[str, str]) -> dict[tuple[str, str], list[tuple[str, int]]]:
        index: dict[tuple[str, str], list[tuple[str, int]]] = {}
        for rel, text in texts.items():
            for polarity, body, line in _directives(text):
                index.setdefault((rel, body), []).append((polarity, line))
        return index

    base_directives = directive_index(base_texts)
    head_directives = directive_index(head_texts)
    for key in sorted(base_directives.keys() & head_directives.keys()):
        base_rows = base_directives[key]
        head_rows = head_directives[key]
        base_polarities = {row[0] for row in base_rows}
        head_polarities = {row[0] for row in head_rows}
        if len(base_polarities) != 1 or len(head_polarities) != 1 or base_polarities == head_polarities:
            continue
        rel, body = key
        findings.append(
            _finding(
                "directive-polarity-flip",
                rel,
                head_rows[0][1],
                message=f"Directive polarity changed for: '{body}'",
            )
        )
    return findings


@dataclass
class RegressionReport:
    base: Report
    head: Report
    delta: int
    new_findings: list[Finding]
    resolved_findings: list[Finding]

    @property
    def new_errors(self) -> list[Finding]:
        return [finding for finding in self.new_findings if finding.severity == "error"]

    def to_dict(self) -> dict:
        return {
            "base": self.base.to_dict(),
            "head": self.head.to_dict(),
            "delta": self.delta,
            "new_findings": [finding.to_dict() for finding in self.new_findings],
            "resolved_findings": [finding.to_dict() for finding in self.resolved_findings],
        }


def compare(
    base_root: Path,
    head_root: Path,
    *,
    suppressions: tuple[Suppression, ...] = (),
) -> RegressionReport:
    # The caller supplies the baseline repository suppressions. Applying the
    # same trusted suppression set to both trees prevents a candidate PR from
    # exempting its own newly introduced findings.
    # Reuse exactly the text that produced each scan's findings. A second,
    # unguarded read could see different text, skip an I/O failure, or follow
    # an instruction alias replaced after scanning.
    base, base_texts = _analyze_with_texts(base_root, suppressions=suppressions)
    head, head_texts = _analyze_with_texts(head_root, suppressions=suppressions)

    base_by_key = {_finding_key(finding): finding for finding in base.findings}
    head_by_key = {_finding_key(finding): finding for finding in head.findings}

    new_keys = head_by_key.keys() - base_by_key.keys()
    resolved_keys = base_by_key.keys() - head_by_key.keys()

    candidate_findings = [head_by_key[key] for key in new_keys]
    for finding in _regression_findings(base_texts, head_texts):
        suppression = _matching_suppression(finding, suppressions)
        if suppression is None:
            candidate_findings.append(finding)
        else:
            head.suppressed_findings.append(SuppressedFinding(finding=finding, suppression=suppression))

    head.suppressed_findings.sort(
        key=lambda item: (
            item.finding.severity != "error",
            item.finding.code,
            item.finding.file,
            item.finding.line or 0,
        )
    )

    new_findings = sorted(
        candidate_findings,
        key=lambda finding: (finding.severity != "error", finding.code, finding.file, finding.line or 0),
    )
    resolved_findings = sorted(
        (base_by_key[key] for key in resolved_keys),
        key=lambda finding: (finding.severity != "error", finding.code, finding.file, finding.line or 0),
    )

    return RegressionReport(
        base=base,
        head=head,
        delta=head.score - base.score,
        new_findings=new_findings,
        resolved_findings=resolved_findings,
    )


def markdown_report(report: RegressionReport) -> str:
    sign = "+" if report.delta > 0 else ""
    status = "✅ No regression" if report.delta >= 0 and not report.new_errors else "⚠️ Regression detected"
    lines = [
        "## AgentConfigScore regression",
        "",
        f"**{status}**",
        "",
        f"| Base | Head | Delta | New findings | Resolved |",
        f"| ---: | ---: | ---: | ---: | ---: |",
        f"| {report.base.score}/100 ({report.base.grade}) | {report.head.score}/100 ({report.head.grade}) | {sign}{report.delta} | {len(report.new_findings)} | {len(report.resolved_findings)} |",
    ]

    if report.new_findings:
        lines.extend(["", "### New findings", ""])
        for finding in report.new_findings:
            location = finding.file + (f":{finding.line}" if finding.line else "")
            lines.append(f"- **{finding.severity.upper()}** `{finding.code}` — {finding.message} (`{location}`)")

    if report.resolved_findings:
        lines.extend(["", "### Resolved findings", ""])
        for finding in report.resolved_findings:
            location = finding.file + (f":{finding.line}" if finding.line else "")
            lines.append(f"- ~~`{finding.code}` — {finding.message} (`{location}`)~~")

    suppressed = report.head.suppressed_findings
    if suppressed:
        lines.extend(["", "### Suppressed findings", ""])
        for item in suppressed:
            finding = item.finding
            location = finding.file + (f":{finding.line}" if finding.line else "")
            suppression = item.suppression
            scope = f"; paths: {', '.join(suppression.paths)}" if suppression.paths else ""
            lines.append(
                f"- `{finding.code}` — {finding.message} (`{location}`) — "
                f"reason: {suppression.reason}; expires: {suppression.expires.isoformat()}{scope}"
            )

    lines.extend(["", "_Generated by AgentConfigScore. Only regressions matter._", ""])
    return "\n".join(lines)
