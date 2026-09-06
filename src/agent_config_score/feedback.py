from __future__ import annotations

from collections import Counter

from . import __version__
from .scanner import Report


CASE_FORM_URL = (
    "https://github.com/LE0-Lin/AgentConfigScore/issues/new"
    "?template=real_world_case.yml"
)


def feedback_markdown(report: Report) -> str:
    """Build a privacy-minimized report that a user can review before sharing."""
    active = Counter(finding.code for finding in report.findings)
    suppressed = Counter(
        item.finding.code for item in report.suppressed_findings
    )

    lines = [
        "# AgentConfigScore real-world case",
        "",
        "> Review this report before sharing it. It intentionally excludes repository",
        "> names, file paths, instruction text, finding messages, and suppression reasons.",
        "",
        "## Generated result",
        "",
        f"- AgentConfigScore version: `{__version__}`",
        f"- Score: **{report.grade} {report.score}/100**",
        f"- Supported instruction files scanned: **{len(report.files)}**",
        f"- Active findings: **{len(report.findings)}**",
        f"- Suppressed findings: **{len(report.suppressed_findings)}**",
        "",
        "### Active rule IDs",
        "",
    ]
    if active:
        lines.extend(f"- `{code}` × {count}" for code, count in sorted(active.items()))
    else:
        lines.append("- None")

    lines.extend(["", "### Suppressed rule IDs", ""])
    if suppressed:
        lines.extend(f"- `{code}` × {count}" for code, count in sorted(suppressed.items()))
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Your observations",
            "",
            "### Outcome",
            "",
            "<!-- Useful finding, false positive, false negative, or setup feedback? -->",
            "",
            "### What happened and why did it matter?",
            "",
            "<!-- Describe the practical effect on your coding-agent workflow. -->",
            "",
            "### Minimal sanitized before/after",
            "",
            "<!-- Include only the minimum instructions needed to reproduce the behavior. -->",
            "",
            "### What did you expect instead?",
            "",
            "<!-- For a useful finding, explain what regression or risk it prevented. -->",
            "",
            "## Privacy checklist",
            "",
            "- [ ] I removed credentials, secrets, personal data, and private repository details.",
            "- [ ] I reviewed every line of this report before sharing it.",
            "",
            f"Submit the reviewed case: {CASE_FORM_URL}",
            "",
        ]
    )
    return "\n".join(lines)
