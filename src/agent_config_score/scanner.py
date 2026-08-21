from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path
import hashlib
import html
import json
import re

from .config import Suppression
from .rules import CATEGORY_CAPS, PATTERN_RULES, RULES_BY_CODE

TARGET_NAMES = {
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".clinerules",
    ".windsurfrules", "copilot-instructions.md",
}
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "dist", "build", ".next",
    "target", "vendor", ".idea", ".vscode", "__pycache__",
}

PATH_CANDIDATE = re.compile(
    r"`([^`\n]{1,160})`|\b((?:src|app|apps|packages|lib|libs|test|tests|docs|scripts|config|configs)/[A-Za-z0-9_./@+\-]+)"
)
DIRECTIVE = re.compile(r"\b(always|never|must|must not|do not|don't)\s+([^.?!\n]{4,120})", re.I)


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    file: str
    line: int | None = None
    penalty: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SuppressedFinding:
    finding: Finding
    suppression: Suppression

    def to_dict(self) -> dict:
        return {
            "finding": self.finding.to_dict(),
            "suppression": self.suppression.to_dict(),
        }


@dataclass
class Report:
    root: str
    files: list[str]
    score: int
    grade: str
    estimated_tokens: int
    duplicate_ratio: float
    findings: list[Finding]
    suppressed_findings: list[SuppressedFinding]

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "files": self.files,
            "score": self.score,
            "grade": self.grade,
            "estimated_tokens": self.estimated_tokens,
            "duplicate_ratio": round(self.duplicate_ratio, 4),
            "findings": [f.to_dict() for f in self.findings],
            "suppressed_findings": [item.to_dict() for item in self.suppressed_findings],
        }


def _finding(code: str, file: str, line: int | None = None, message: str | None = None) -> Finding:
    rule = RULES_BY_CODE[code]
    return Finding(
        severity=rule.severity,
        code=rule.code,
        message=rule.summary if message is None else message,
        file=file,
        line=line,
        penalty=rule.penalty,
    )


def _ignore_patterns(root: Path) -> list[str]:
    p = root / ".agentconfigscoreignore"
    if not p.exists():
        return []
    return [
        line.strip() for line in p.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _ignored(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch(rel, pat) or fnmatch(rel + "/", pat) for pat in patterns)


def discover(root: Path) -> list[Path]:
    root = root.resolve()
    patterns = _ignore_patterns(root)
    found: list[Path] = []
    for path in root.rglob("*"):
        rel_path = path.relative_to(root)
        rel = rel_path.as_posix()
        if any(part in SKIP_DIRS for part in rel_path.parts) or _ignored(rel, patterns):
            continue
        if not path.is_file():
            continue
        if path.name in TARGET_NAMES:
            found.append(path)
        elif rel.startswith((".cursor/rules/", ".claude/", ".github/instructions/")) and path.suffix.lower() in {".md", ".mdc"}:
            found.append(path)
    return sorted(set(found), key=lambda p: p.relative_to(root).as_posix())


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    ascii_chars = sum(ord(c) < 128 for c in text)
    return max(1, round(ascii_chars / 4 + (len(text) - ascii_chars) / 1.7))


def _line(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _normalized_line(line: str) -> str | None:
    line = re.sub(r"[`*_>#-]", "", line.strip().lower())
    line = re.sub(r"\s+", " ", line).strip()
    if not line or line.startswith("#") or len(line) < 24:
        return None
    return line


def _candidate_paths(text: str):
    for m in PATH_CANDIDATE.finditer(text):
        value = (m.group(1) or m.group(2) or "").strip().rstrip(".,:;")
        if not value or any(c.isspace() for c in value):
            continue
        if value.startswith(("http://", "https://", "$", "~", "./.git")):
            continue
        if "://" in value or "|" in value or any(c in value for c in "*<>{}"):
            continue
        if "/" not in value and "." not in Path(value).name:
            continue
        yield value, _line(text, m.start())


def _directives(text: str):
    for m in DIRECTIVE.finditer(text):
        op = m.group(1).lower()
        body = re.sub(r"\b(the|a|an)\b", "", m.group(2).strip().lower())
        body = re.sub(r"\s+", " ", body).strip()
        polarity = "neg" if op in {"never", "must not", "do not", "don't"} else "pos"
        yield polarity, body, _line(text, m.start())


def _matching_suppression(finding: Finding, suppressions: tuple[Suppression, ...]) -> Suppression | None:
    for suppression in suppressions:
        if suppression.applies_to(finding.code, finding.file):
            return suppression
    return None


def analyze(root: Path, *, suppressions: tuple[Suppression, ...] = ()) -> Report:
    root = root.resolve()
    files = discover(root)
    texts: dict[Path, str] = {}
    findings: list[Finding] = []
    total_tokens = 0

    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(_finding("read-error", rel, message=str(exc)))
            continue
        texts[path] = text
        tokens = estimate_tokens(text)
        total_tokens += tokens
        if tokens > 8000:
            findings.append(_finding("context-too-large", rel, message=f"Estimated {tokens:,} tokens; large persistent instructions waste context"))
        elif tokens > 5000:
            findings.append(_finding("context-large", rel, message=f"Estimated {tokens:,} tokens; consider trimming persistent instructions"))

        for pattern_rule in PATTERN_RULES:
            for match in pattern_rule.pattern.finditer(text):
                findings.append(_finding(pattern_rule.rule.code, rel, _line(text, match.start())))

        seen_refs: set[tuple[str, int]] = set()
        for candidate, lineno in _candidate_paths(text):
            key = (candidate, lineno)
            if key in seen_refs:
                continue
            seen_refs.add(key)
            if not (root / candidate).exists():
                findings.append(_finding("dead-path", rel, lineno, f"Referenced path does not exist: {candidate}"))

    line_locations: dict[str, list[tuple[str, int]]] = defaultdict(list)
    total_meaningful = 0
    for path, text in texts.items():
        rel = path.relative_to(root).as_posix()
        for lineno, raw in enumerate(text.splitlines(), 1):
            normalized = _normalized_line(raw)
            if normalized:
                total_meaningful += 1
                line_locations[normalized].append((rel, lineno))
    duplicates = sum(len(v) for v in line_locations.values() if len({r[0] for r in v}) > 1)
    duplicate_ratio = duplicates / total_meaningful if total_meaningful else 0.0
    if duplicate_ratio >= 0.35:
        findings.append(_finding("high-duplication", "(repo)", message=f"{duplicate_ratio:.0%} of meaningful instruction lines are duplicated across files"))
    elif duplicate_ratio >= 0.15:
        findings.append(_finding("duplication", "(repo)", message=f"{duplicate_ratio:.0%} of meaningful instruction lines are duplicated across files"))

    directives: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for path, text in texts.items():
        rel = path.relative_to(root).as_posix()
        for polarity, body, lineno in _directives(text):
            directives[body].append((polarity, rel, lineno))
    for body, rows in directives.items():
        if {row[0] for row in rows} >= {"pos", "neg"}:
            files_str = ", ".join(sorted({row[1] for row in rows}))
            findings.append(_finding("contradiction", "(repo)", message=f"Conflicting directives about: '{body}' ({files_str})"))

    rels = [p.relative_to(root).as_posix() for p in files]
    if len(files) >= 2 and "AGENTS.md" not in rels:
        findings.append(_finding("no-agents-md", "(repo)"))
    if not files:
        findings.append(_finding("no-config", "(repo)"))

    active_findings: list[Finding] = []
    suppressed_findings: list[SuppressedFinding] = []
    for finding in findings:
        suppression = _matching_suppression(finding, suppressions)
        if suppression is None:
            active_findings.append(finding)
        else:
            suppressed_findings.append(SuppressedFinding(finding=finding, suppression=suppression))
    findings = active_findings

    used = Counter()
    penalty = 0
    for finding in findings:
        rule = RULES_BY_CODE.get(finding.code)
        category = rule.category if rule is not None else "other"
        cap = CATEGORY_CAPS.get(category, CATEGORY_CAPS["other"])
        applied = min(finding.penalty, max(0, cap - used[category]))
        used[category] += applied
        penalty += applied

    score = max(0, 100 - penalty)
    grade = "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F"
    order = {"error": 0, "warning": 1, "info": 2}
    return Report(
        root=str(root), files=rels, score=score, grade=grade,
        estimated_tokens=total_tokens, duplicate_ratio=duplicate_ratio,
        findings=sorted(findings, key=lambda f: (order.get(f.severity, 3), f.file, f.line or 0)),
        suppressed_findings=sorted(
            suppressed_findings,
            key=lambda item: (
                order.get(item.finding.severity, 3),
                item.finding.file,
                item.finding.line or 0,
                item.finding.code,
            ),
        ),
    )


def badge_svg(report: Report) -> str:
    color = {"A": "#4c1", "B": "#97ca00", "C": "#dfb317", "D": "#fe7d37", "F": "#e05d44"}[report.grade]
    value = f"{report.grade} {report.score}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="146" height="20" role="img" aria-label="agent config: {value}">
<rect width="88" height="20" rx="3" fill="#555"/><rect x="88" width="58" height="20" rx="3" fill="{color}"/>
<g fill="#fff" text-anchor="middle" font-family="Verdana,sans-serif" font-size="11"><text x="44" y="14">agent config</text><text x="117" y="14">{value}</text></g></svg>'''


def html_report(report: Report) -> str:
    rows = []
    for f in report.findings:
        loc = html.escape(f.file + (f":{f.line}" if f.line else ""))
        rows.append(f"<tr><td>{html.escape(f.severity)}</td><td><code>{html.escape(f.code)}</code></td><td>{html.escape(f.message)}</td><td><code>{loc}</code></td></tr>")
    suppressed_rows = []
    for item in report.suppressed_findings:
        f = item.finding
        loc = html.escape(f.file + (f":{f.line}" if f.line else ""))
        reason = html.escape(item.suppression.reason)
        expires = html.escape(item.suppression.expires.isoformat())
        suppressed_rows.append(
            f"<tr><td><code>{html.escape(f.code)}</code></td><td>{html.escape(f.message)}</td><td><code>{loc}</code></td><td>{reason}</td><td>{expires}</td></tr>"
        )
    file_rows = "".join(f"<li><code>{html.escape(p)}</code></li>" for p in report.files) or "<li>No supported files found</li>"
    fingerprint = hashlib.sha256(json.dumps(report.to_dict(), sort_keys=True).encode()).hexdigest()[:12]
    suppressed_section = ""
    if suppressed_rows:
        suppressed_section = (
            "<h2>Suppressed findings</h2>"
            "<table><tr><th>Rule</th><th>Message</th><th>Location</th><th>Reason</th><th>Expires</th></tr>"
            + "".join(suppressed_rows)
            + "</table>"
        )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AgentConfigScore report</title>
<style>body{{margin:0;background:#0b1020;color:#edf3ff;font:15px/1.55 system-ui,sans-serif}}main{{max-width:1000px;margin:auto;padding:40px 20px}}h1{{font-size:42px}}.score{{font-size:52px;font-weight:800}}.muted{{color:#93a4bd}}table{{width:100%;border-collapse:collapse;background:#121a2f}}th,td{{padding:12px;border-bottom:1px solid #263451;text-align:left;vertical-align:top}}code{{color:#cfe0ff}}ul{{background:#121a2f;padding:18px 18px 18px 40px}}</style></head><body><main>
<div class="score">{report.grade} · {report.score}/100</div><h1>AgentConfigScore</h1><p class="muted">{len(report.files)} config files · {report.estimated_tokens:,} estimated tokens · {report.duplicate_ratio:.0%} duplication · {len(report.suppressed_findings)} suppressed</p>
<h2>Findings</h2><table><tr><th>Severity</th><th>Rule</th><th>Message</th><th>Location</th></tr>{''.join(rows) or '<tr><td colspan="4">No findings 🎉</td></tr>'}</table>
{suppressed_section}<h2>Files scanned</h2><ul>{file_rows}</ul><p class="muted">Report fingerprint {fingerprint} · Generated by AgentConfigScore</p></main></body></html>'''
