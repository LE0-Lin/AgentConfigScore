from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath, PureWindowsPath
import hashlib
import html
import json
import re

from .config import Suppression
from .rules import CATEGORY_CAPS, PATTERN_RULES, RULES_BY_CODE

AGENTS_FILENAMES = {"AGENTS.md", "AGENTS.override.md"}
TARGET_NAMES = AGENTS_FILENAMES | {
    "CLAUDE.md", "GEMINI.md", ".cursorrules", ".clinerules",
    ".windsurfrules", "copilot-instructions.md",
}
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "dist", "build", ".next",
    "target", "vendor", ".idea", ".vscode", "__pycache__",
}

PATH_CANDIDATE = re.compile(
    r"`([^`\n]{1,160})`|\b((?:src|app|apps|packages|lib|libs|test|tests|docs|scripts|config|configs)/[A-Za-z0-9_./@+\-]+)"
)
PATH_EXTENSIONS = {
    ".bash", ".c", ".cc", ".cfg", ".conf", ".cpp", ".cs", ".css",
    ".fish", ".go", ".gradle", ".h", ".hpp", ".html", ".ini", ".java",
    ".js", ".json", ".jsx", ".kt", ".kts", ".lock", ".md", ".mdc",
    ".php", ".proto", ".ps1", ".py", ".pyi", ".rb", ".rs", ".scss",
    ".sh", ".sql", ".svelte", ".swift", ".toml", ".ts", ".tsx", ".txt",
    ".vue", ".xml", ".yaml", ".yml", ".zsh",
}
PATH_BASENAMES = {
    "Dockerfile", "Gemfile", "Justfile", "LICENSE", "Makefile", "Procfile",
    "Rakefile",
}
NON_PATH_PREFIXES = ("origin/", "refs/", "feat/", "feature/", "fix/", "release/")
DIRECTIVE = re.compile(r"\b(always|never|must not|must|do not|don't)\s+([^.?!\n]{4,120})", re.I)
DANGER_NEGATION = re.compile(
    r"\b(?:never|do\s+not|don't|must\s+not|should\s+not|avoid|forbidden|prohibited|unsafe\s+example)\b",
    re.I,
)
DANGER_NEGATION_EXCEPTION = re.compile(r"\b(?:but|however|except|unless)\b", re.I)
DANGER_DOUBLE_NEGATIVE = re.compile(
    r"\b(?:(?:do\s+not|don't)\s+hesitate(?:\s+to)?|(?:never|do\s+not|don't|must\s+not)\s+avoid)\b",
    re.I,
)


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
    # Keep the caller's path identity instead of resolving filesystem aliases.
    # macOS may rewrite /var to /private/var and Windows may expand 8.3 paths;
    # callers should still be able to make discovered files relative to the
    # absolute root they supplied.
    root = root.absolute()
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


def _dangerous_command_is_prohibited(text: str, index: int) -> bool:
    """Ignore dangerous commands that are explicitly prohibited in the same clause."""
    line_start = text.rfind("\n", 0, index) + 1
    line_end = text.find("\n", index)
    if line_end == -1:
        line_end = len(text)
    prefix = text[line_start:index]
    clause_prefix = re.split(r"[.!?;]", prefix)[-1]
    clause_suffix = re.split(r"[.!?;]", text[index:line_end], maxsplit=1)[0]
    clause_prefix = re.sub(r"[`*_>#]", " ", clause_prefix)
    clause_suffix = re.sub(r"[`*_>#]", " ", clause_suffix)
    if DANGER_DOUBLE_NEGATIVE.search(clause_prefix):
        return False
    negations = list(DANGER_NEGATION.finditer(clause_prefix))
    if not negations:
        return False
    after_negation = clause_prefix[negations[-1].end():] + clause_suffix
    return DANGER_NEGATION_EXCEPTION.search(after_negation) is None


def _normalized_line(line: str) -> str | None:
    line = re.sub(r"[`*_>#-]", "", line.strip().lower())
    line = re.sub(r"\s+", " ", line).strip()
    if not line or line.startswith("#") or len(line) < 24:
        return None
    return line


def _looks_like_repository_path(value: str) -> bool:
    """Reject code symbols, package names, URLs, and branch names before probing."""
    normalized = value.replace("\\", "/")
    if normalized.startswith("@") or normalized.endswith("/"):
        return False
    if normalized.lower().startswith(NON_PATH_PREFIXES):
        return False
    if re.match(r"^[A-Za-z0-9-]+\.(?:com|dev|io|net|org)/", normalized, re.I):
        return False
    if any(char in normalized for char in "()[]=,;:#?'\""):
        return False
    if any(
        part.lower() in {"foo", "bar", "baz", "example", "sample"}
        or re.search(r"(?:NameHere|Placeholder)", part, re.I)
        for part in PurePosixPath(normalized).parts
    ):
        return False

    name = PurePosixPath(normalized).name
    if name in PATH_BASENAMES:
        return True
    raw_suffix = PurePosixPath(name).suffix
    if raw_suffix == raw_suffix.lower() and raw_suffix in PATH_EXTENSIONS:
        # A bare `service.py` usually describes a naming convention, not a
        # repository-root file. Require a directory component for ordinary
        # source files; well-known root files are handled above.
        return "/" in normalized

    # Extensionless slash-delimited tokens are too ambiguous: they are often
    # package imports, RPC names, branch prefixes, or prose shorthand. The
    # dead-path rule intentionally favors precision over guessing at those.
    return False


def _inside_markdown_fence(text: str, index: int) -> bool:
    fence_count = 0
    for line in text[:index].splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence_count += 1
    return fence_count % 2 == 1


def _candidate_paths(text: str):
    for m in PATH_CANDIDATE.finditer(text):
        if _inside_markdown_fence(text, m.start()):
            continue
        if m.group(2) and m.start() > 0 and text[m.start() - 1] in "/\\.~%":
            # The broad unquoted matcher can otherwise start in the middle of
            # a URL, home-directory path, or absolute platform path.
            continue
        value = (m.group(1) or m.group(2) or "").strip().rstrip(".,:;")
        if not value or any(c.isspace() for c in value):
            continue
        if value.startswith(("http://", "https://", "$", "~", "./.git")):
            continue
        if "://" in value or "|" in value or any(c in value for c in "*<>{}"):
            continue
        if not _looks_like_repository_path(value):
            continue
        yield value.replace("\\", "/"), _line(text, m.start())


def _repo_candidate(root: Path, base: Path, candidate: str) -> Path | None:
    # Never probe absolute, Windows drive-qualified, or escaping paths. The
    # scanner is about repository instructions, not the caller's filesystem.
    windows_candidate = PureWindowsPath(candidate)
    if Path(candidate).is_absolute() or windows_candidate.is_absolute() or windows_candidate.drive:
        return None
    target = (base / candidate).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def _candidate_exists(
    root: Path,
    source: Path,
    candidate: str,
    repository_paths: set[str] | None = None,
) -> bool | None:
    # Repository-root relative paths remain the primary interpretation. For a
    # nested AGENTS-family file, also accept a path relative to that file's
    # directory, which is the root of its instruction scope.
    bases = [root]
    if source.name in AGENTS_FILENAMES and source.parent != root:
        # Instructions often use paths relative to a package root rather than
        # the exact directory containing a nested AGENTS.md. Accept any
        # in-repository ancestor interpretation to avoid false dead paths.
        current = source.parent
        while current != root:
            bases.append(current)
            current = current.parent

    checked = False
    for base in bases:
        target = _repo_candidate(root, base, candidate)
        if target is None:
            continue
        checked = True
        if target.exists():
            return True
    if repository_paths is not None:
        normalized = candidate.lstrip("./")
        if any(path == normalized or path.endswith("/" + normalized) for path in repository_paths):
            return True
    return False if checked else None


def _repository_path_index(root: Path) -> set[str]:
    paths: set[str] = set()
    for path in root.rglob("*"):
        rel_path = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel_path.parts):
            continue
        paths.add(rel_path.as_posix())
    return paths


def _directives(text: str):
    for m in DIRECTIVE.finditer(text):
        op = m.group(1).lower()
        body = re.sub(r"\b(the|a|an)\b", "", m.group(2).strip().lower())
        body = re.sub(r"\s+", " ", body).strip()
        polarity = "neg" if op in {"never", "must not", "do not", "don't"} else "pos"
        yield polarity, body, _line(text, m.start())


def _agents_precedence_resolves(left: str, right: str) -> bool:
    # Different AGENTS-family files cannot create an ambiguous directive for
    # one Codex target: directory scopes are disjoint or deeper instructions
    # have precedence; AGENTS.override.md also has deterministic same-directory
    # priority over AGENTS.md. A contradiction inside one file remains real.
    left_path = PurePosixPath(left)
    right_path = PurePosixPath(right)
    return (
        left != right
        and left_path.name in AGENTS_FILENAMES
        and right_path.name in AGENTS_FILENAMES
    )


def _unresolved_contradiction_files(rows: list[tuple[str, str, int]]) -> set[str]:
    positives = [row for row in rows if row[0] == "pos"]
    negatives = [row for row in rows if row[0] == "neg"]
    conflicts: set[str] = set()
    for positive in positives:
        for negative in negatives:
            if _agents_precedence_resolves(positive[1], negative[1]):
                continue
            conflicts.add(positive[1])
            conflicts.add(negative[1])
    return conflicts


def _matching_suppression(finding: Finding, suppressions: tuple[Suppression, ...]) -> Suppression | None:
    for suppression in suppressions:
        if suppression.applies_to(finding.code, finding.file):
            return suppression
    return None


def analyze(root: Path, *, suppressions: tuple[Suppression, ...] = ()) -> Report:
    root = root.resolve()
    files = discover(root)
    repository_paths = _repository_path_index(root)
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
        if not text.strip():
            findings.append(_finding("empty-instructions", rel))
        tokens = estimate_tokens(text)
        total_tokens += tokens
        if tokens > 8000:
            findings.append(_finding("context-too-large", rel, message=f"Estimated {tokens:,} tokens; large persistent instructions waste context"))
        elif tokens > 5000:
            findings.append(_finding("context-large", rel, message=f"Estimated {tokens:,} tokens; consider trimming persistent instructions"))

        for pattern_rule in PATTERN_RULES:
            for match in pattern_rule.pattern.finditer(text):
                if (
                    pattern_rule.rule.category == "danger"
                    and _dangerous_command_is_prohibited(text, match.start())
                ):
                    continue
                findings.append(_finding(pattern_rule.rule.code, rel, _line(text, match.start())))

        seen_refs: set[tuple[str, int]] = set()
        for candidate, lineno in _candidate_paths(text):
            key = (candidate, lineno)
            if key in seen_refs:
                continue
            seen_refs.add(key)
            exists = _candidate_exists(root, path, candidate, repository_paths)
            if exists is False:
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
        conflict_files = _unresolved_contradiction_files(rows)
        if conflict_files:
            files_str = ", ".join(sorted(conflict_files))
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
    if any(finding.severity == "error" for finding in findings):
        score = min(score, 89)
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
<p><strong>Scope:</strong> deterministic rule matches only. This score is not semantic quality certification.</p>
<h2>Findings</h2><table><tr><th>Severity</th><th>Rule</th><th>Message</th><th>Location</th></tr>{''.join(rows) or '<tr><td colspan="4">No findings 🎉</td></tr>'}</table>
{suppressed_section}<h2>Files scanned</h2><ul>{file_rows}</ul><p class="muted">Report fingerprint {fingerprint} · Generated by AgentConfigScore</p></main></body></html>'''
