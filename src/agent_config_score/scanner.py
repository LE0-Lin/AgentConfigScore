from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath, PureWindowsPath
import errno
import hashlib
import html
import ipaddress
import json
import os
import re
import shlex
import stat
from urllib.parse import unquote, urlsplit

from .config import Suppression
from .provenance import ToolIdentity, capture_tool_identity
from .rules import CATEGORY_CAPS, PATTERN_RULES, RULES_BY_CODE

AGENTS_FILENAMES = {"AGENTS.md", "AGENTS.override.md"}
AGENTS_FILENAMES_CASEFOLD = {name.casefold() for name in AGENTS_FILENAMES}
TARGET_NAMES = AGENTS_FILENAMES | {
    "CLAUDE.md", "GEMINI.md", ".cursorrules", ".clinerules",
    ".windsurfrules", "copilot-instructions.md",
}
TARGET_NAMES_CASEFOLD = {name.casefold() for name in TARGET_NAMES}
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "dist", "build", ".next",
    "target", "vendor", ".idea", ".vscode", "__pycache__",
}
# Instruction discovery skips generated trees. Path existence is a different
# question: real source code can also live in directories named build/dist.
PATH_INDEX_SKIP_DIRS = SKIP_DIRS - {"build", "dist", "target", ".next"}

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
    r"\b(?:never|do\s+not|don't|must\s+not)\s+(?:hesitate|avoid|forget|fail|refuse|neglect)\b",
    re.I,
)

PARSED_COMMAND_RULES = {"rm-rf", "git-clean-force", "docker-system-prune"}

FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)$")
LIST_ITEM = re.compile(r"^( {0,3})([-+*]|\d{1,9}[.)])[ \t]+")
SETEXT_HEADING = re.compile(r" {0,3}(?:=+|-+)[ \t]*")
THEMATIC_BREAK = re.compile(r" {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})")
BLOCK_PROHIBITION = re.compile(
    r"(?:(?:never|do\s+not|don't|must\s+not)\s+"
    r"(?:run|execute|use|follow)\s+(?:(?:any\s+of\s+)?(?:the\s+)?following|these)\s+"
    r"(?:commands|instructions)(?:\s+under\s+any\s+circumstances)?"
    r"|(?:the\s+)?following\s+(?:commands|instructions)\s+are\s+(?:forbidden|prohibited))\s*:",
    re.I,
)

# A bounded, complete-clause grammar, not a bag of workflow keywords. Require
# an affirmative reporting directive together with evidence of concealment.
_PROSE_DIRECTIVE_PREFIX = r"(?:(?:please|always)\s+|you\s+(?:must|should)\s+)?"
_TEST_SUBJECT = r"(?:(?:all|the)\s+)?(?:tests?|test\s+suite)"
_TEST_PASS_CLAIM = (
    r"(?:report|declare|claim)\s+(?:that\s+)?" + _TEST_SUBJECT
    + r"\s+(?:(?:as|are|were|have)\s+)?(?:passed|passing|successful)"
)
_SUCCESS_CLAIM = r"(?:report|declare|claim)\s+success|" + _TEST_PASS_CLAIM
_EXPLICIT_TEST_FAILURE = _TEST_SUBJECT + r"\s+(?:fail|fails|failed)"
_TEST_FAILURE = _EXPLICIT_TEST_FAILURE + r"|they\s+(?:fail|failed)"
FALSE_SUCCESS_DIRECTIVE = re.compile(
    _PROSE_DIRECTIVE_PREFIX + r"(?:ignore|disregard)\s+(?:(?:all|any|the)\s+)?"
    r"(?:errors|failures|test\s+failures|failed\s+tests)\s+and\s+"
    r"(?:(?:then|still|always)\s+)?(?:" + _SUCCESS_CLAIM + r")"
    r"|" + _PROSE_DIRECTIVE_PREFIX + _TEST_PASS_CLAIM + r"\s+(?:"
    r"even\s+(?:if|when)\s+(?:" + _TEST_FAILURE + r")"
    r"|without\s+(?:running|executing)\s+(?:" + _TEST_SUBJECT + r"|them)"
    r"|despite\s+(?:test\s+failures|failing\s+tests))"
    r"|(?:if|when)\s+(?:" + _EXPLICIT_TEST_FAILURE + r"),\s*"
    + _PROSE_DIRECTIVE_PREFIX + r"(?:still\s+)?(?:" + _SUCCESS_CLAIM + r")",
    re.I,
)

_ENVIRONMENT_VARIABLES = r"(?:environment\s+variables?|env\s+vars?)(?:\s+values?)?"
_BULK_ENVIRONMENT = (
    r"(?:(?:all(?:\s+of)?(?:\s+the)?|every)\s+"
    r"(?:(?:raw|unfiltered|unredacted)\s+)?" + _ENVIRONMENT_VARIABLES
    + r"|(?:the\s+)?(?:entire|full|complete|raw|unfiltered)\s+process\s+environment)"
)
BROAD_ENVIRONMENT_TRANSFER = re.compile(
    _PROSE_DIRECTIVE_PREFIX + r"(?:upload|send|post|transmit|forward)\s+"
    + _BULK_ENVIRONMENT + r"\s+to\s+(?P<destination>.+)", re.I,
)
UPLOAD_DESTINATION = re.compile(
    r"(?:(?:the|a|an|our|your)\s+)?"
    r"(?:(?:diagnostics?|telemetry|support|debug|remote|external|reporting|analytics)\s+){0,2}"
    r"(?:endpoint|server|service|collector|api)", re.I,
)


@dataclass(frozen=True)
class _ProhibitionScope:
    start: int
    end: int
    has_exception: bool


@dataclass
class _InstructionLine:
    start: int
    end: int
    kind: str = "prose"
    body_start: int | None = None
    prohibition: _ProhibitionScope | None = None


@dataclass(frozen=True)
class _InstructionContext:
    """Shared source offsets and narrowly scoped Markdown context for one file."""

    text: str
    lines: tuple[_InstructionLine, ...]
    starts: tuple[int, ...]

    def line_index(self, index: int) -> int:
        return bisect_right(self.starts, index) - 1

    def inside_fence(self, index: int) -> bool:
        if not self.lines:
            return False
        row = self.lines[self.line_index(index)]
        return row.kind in {"code", "fence"}

    def command_is_prohibited(self, index: int) -> bool:
        if not self.lines:
            return False
        row = self.lines[self.line_index(index)]
        if row.prohibition is None:
            return False
        # An exception anywhere in the block makes its intent ambiguous. Do
        # not convert it into a blanket exemption for every command below it.
        if row.prohibition.has_exception:
            return False
        prefix = self.text[row.body_start if row.body_start is not None else row.start:index]
        if row.kind == "list":
            # Only direct command entries inherit a list prohibition. Prose
            # like "Instead run ..." is a new action, not a negative example.
            return re.fullmatch(r"[ \t`\"']*", prefix) is not None
        return re.search(r"\b(?:always|must|run|execute|use|follow)\b", prefix, re.I) is None


def _instruction_context(text: str) -> _InstructionContext:
    """Parse top-level fences and explicit, immediately adjacent prohibitions.

    This is not a full Markdown AST or a natural-language intent classifier.
    Unlabeled code stays active for danger rules, and unclosed fences never
    acquire an inherited prohibition.
    """
    rows: list[_InstructionLine] = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        rows.append(_InstructionLine(offset, offset + len(raw)))
        offset += len(raw)

    fence: tuple[str, int, int, int | None] | None = None
    pending_intro: int | None = None
    blank_count = 0
    list_intro: int | None = None
    list_indent: int | None = None
    list_marker: str | None = None
    list_rows: list[int] = []

    def prohibition_scope(start: int, end: int) -> _ProhibitionScope:
        return _ProhibitionScope(start, end, DANGER_NEGATION_EXCEPTION.search(text[start:end]) is not None)

    def finish_list() -> None:
        nonlocal list_intro, list_indent, list_marker
        if list_intro is not None and list_rows:
            span = prohibition_scope(rows[list_intro].start, rows[list_rows[-1]].end)
            for item in list_rows:
                rows[item].prohibition = span
        list_rows.clear()
        list_intro = list_indent = list_marker = None

    for number, row in enumerate(rows):
        raw = text[row.start:row.end].rstrip("\r\n")
        if fence is not None:
            marker, length, opener, intro = fence
            if re.fullmatch(r" {0,3}" + re.escape(marker) + r"{" + str(length) + r",}[ \t]*", raw):
                row.kind = "fence"
                if intro is not None:
                    span = prohibition_scope(rows[intro].start, row.end)
                    for body in rows[opener + 1:number]:
                        body.prohibition = span
                fence = None
            else:
                row.kind = "code"
            continue

        item = LIST_ITEM.match(raw)
        if list_rows:
            if (item is not None and len(item.group(1)) == list_indent
                    and item.group(2)[-1] == list_marker):
                row.kind = "list"
                row.body_start = row.start + item.end()
                list_rows.append(number)
                continue
            finish_list()

        if not raw.strip():
            blank_count += 1
            if blank_count > 1:
                pending_intro = None
            continue

        opener = FENCE_OPEN.fullmatch(raw)
        if opener is not None and not (opener.group(1)[0] == "`" and "`" in opener.group(2)):
            row.kind = "fence"
            fence = (opener.group(1)[0], len(opener.group(1)), number, pending_intro)
            pending_intro = None
            blank_count = 0
            continue

        if (number and SETEXT_HEADING.fullmatch(raw) and rows[number - 1].kind == "prose"
                and text[rows[number - 1].start:rows[number - 1].end].strip()):
            rows[number - 1].kind = row.kind = "heading"
        elif re.match(r"^ {0,3}#{1,6}(?:\s|$)", raw):
            row.kind = "heading"
        elif THEMATIC_BREAK.fullmatch(raw):
            row.kind = "boundary"
        elif item is not None:
            row.kind = "list"
            row.body_start = row.start + item.end()
            if pending_intro is not None:
                list_intro = pending_intro
                list_indent = len(item.group(1))
                list_marker = item.group(2)[-1]
                list_rows.append(number)
                pending_intro = None
                blank_count = 0
                continue

        label = raw[item.end():] if item is not None else raw
        label = re.sub(r"[*_]", "", label).strip()
        supported_label = row.kind not in {"heading", "boundary"} and not raw.startswith(("    ", "\t"))
        pending_intro = number if supported_label and BLOCK_PROHIBITION.fullmatch(label) else None
        blank_count = 0

    finish_list()
    return _InstructionContext(text, tuple(rows), tuple(row.start for row in rows))


def _command_words(text: str, index: int) -> list[str]:
    """Read one bounded shell fragment without executing or expanding it."""
    fragment = text[index:index + 1000]
    # Honor explicit continuations but never borrow options from the next line.
    fragment = fragment.replace("\\\r\n", " ").replace("\\\n", " ").split("\n", 1)[0]
    if index and text[index - 1] in "`\"'":
        fragment = fragment.split(text[index - 1], 1)[0]
    else:
        fragment = fragment.split("`", 1)[0]
    # Instruction prose commonly appends a sentence-ending period to a command.
    fragment = fragment.strip().removesuffix(".")
    lexer = shlex.shlex(fragment, posix=True, punctuation_chars=";|&()<>")
    lexer.whitespace_split = True
    words: list[str] = []
    try:
        for word in lexer:
            if word and all(char in ";|&()<>" for char in word):
                break
            words.append(word)
    except ValueError:
        # Prose following a valid command can contain unmatched apostrophes.
        # Preserve complete tokens already read; do not guess the broken token.
        pass
    return words


def _command_options(code: str, words: list[str]) -> tuple[bool, str]:
    """Interpret options, their values, terminators, and execution modes."""
    prefix_size = {"rm-rf": 1, "git-clean-force": 2, "docker-system-prune": 3}[code]
    arguments = words[prefix_size:]
    flags: set[str] = set()
    force_mode = False
    consumed_options: list[str] = []
    skip_value = False
    long_flags = {
        "rm-rf": {"--recursive": "r", "--force": "f"},
        "git-clean-force": {"--force": "f",
                            "--dry-run": "n", "--interactive": "i"},
        "docker-system-prune": {"--all": "a", "--force": "f"},
    }[code]
    for argument in arguments:
        if skip_value:
            skip_value = False
            continue
        if argument == "--":
            break
        if argument in {"--help", "--version"}:
            return False, ""
        if code == "git-clean-force" and argument in {"-e", "--exclude"}:
            skip_value = True
            continue
        if code == "git-clean-force" and argument.startswith(("--exclude=", "-e")):
            continue
        if code == "docker-system-prune" and argument == "--filter":
            skip_value = True
            continue
        if code == "docker-system-prune" and argument.startswith("--filter="):
            continue
        if code == "rm-rf" and argument.startswith("--interactive"):
            if argument in {"--interactive", "--interactive=always", "--interactive=once"}:
                force_mode = False
                consumed_options.append(argument)
            elif argument == "--interactive=never":
                force_mode = "f" in flags
                consumed_options.append(argument)
            continue
        if argument in long_flags:
            options = long_flags[argument]
        elif re.fullmatch(r"-[a-zA-Z]+", argument):
            options = argument[1:]
        else:
            # Stop at prose or operands; options inside later prose are not
            # command arguments. Explicit GNU-style options-after-operands are
            # outside this conservative grammar.
            break
        consumed_options.append(argument)
        if code == "git-clean-force" and "e" in options:
            skip_value = options.endswith("e")
            options = options.split("e", 1)[0]
        for option in options:
            flags.add(option)
            if option == "f":
                force_mode = True
            elif code == "rm-rf" and option in {"i", "I"}:
                force_mode = False
    if code == "rm-rf":
        risky = bool(flags & {"r", "R"}) and force_mode
    elif code == "git-clean-force":
        risky = {"f", "d"} <= flags and not flags & {"n", "i"}
    else:
        risky = {"a", "f"} <= flags
    return risky, " ".join([*words[:prefix_size], *consumed_options])


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
    tool: ToolIdentity | None = None

    def to_dict(self) -> dict:
        return {
            "tool": self.tool.to_dict() if self.tool is not None else None,
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


def _scanner_source_target(root: Path, path: Path) -> Path:
    """Validate selected file sources without exposing target/error details."""
    try:
        boundary = root.resolve(strict=True)
        target = path.resolve(strict=True)
    except RuntimeError as exc:  # pathlib symlink loops on Python 3.10-3.12
        raise OSError(errno.ELOOP, "Unable to safely resolve scanner source") from exc
    except OSError as exc:
        raise OSError(exc.errno, "Unable to safely resolve scanner source") from exc
    if not target.is_relative_to(boundary):
        raise OSError(errno.EPERM, "Scanner source must remain inside the repository")
    try:
        regular = stat.S_ISREG(target.stat().st_mode)
    except OSError as exc:
        raise OSError(exc.errno, "Unable to inspect scanner source") from exc
    if not regular:
        raise OSError(errno.EINVAL, "Scanner source must be a regular file")
    return target


def _read_scanner_source(root: Path, path: Path) -> str:
    # Revalidate at read time and open the resolved in-repository target, not
    # an alias that may have changed since discovery. This is not an atomic
    # filesystem sandbox: concurrent replacement of parents/targets is possible.
    target = _scanner_source_target(root, path)
    try:
        return target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise OSError(exc.errno, "Unable to read scanner source") from exc


def _ignore_patterns(root: Path) -> list[str]:
    p = root / ".agentconfigscoreignore"
    try:
        p.lstat()  # A dangling link is not the same as an absent ignore file.
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise OSError(exc.errno, "Unable to inspect scanner ignore file") from exc
    return [
        line.strip() for line in _read_scanner_source(root, p).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _ignored(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch(rel, pat) or fnmatch(rel + "/", pat) for pat in patterns)


def _is_agents_filename(name: str) -> bool:
    return name.casefold() in AGENTS_FILENAMES_CASEFOLD


def _prefer_canonical_name(candidate: Path, current: Path) -> bool:
    """Choose the documented spelling when case variants coexist on Linux."""
    candidate_is_canonical = candidate.name in TARGET_NAMES
    current_is_canonical = current.name in TARGET_NAMES
    if candidate_is_canonical != current_is_canonical:
        return candidate_is_canonical
    return candidate.name < current.name


def discover(root: Path) -> list[Path]:
    # Keep the caller's path identity instead of resolving filesystem aliases.
    # macOS may rewrite /var to /private/var and Windows may expand 8.3 paths;
    # callers should still be able to make discovered files relative to the
    # absolute root they supplied.
    root = root.absolute()
    boundary = root.resolve()
    patterns = _ignore_patterns(root)
    found: dict[str, Path] = {}

    def select(path: Path) -> None:
        rel = path.relative_to(root).as_posix()
        if _ignored(rel, patterns):
            return
        if (path.name.casefold() in TARGET_NAMES_CASEFOLD
                or (rel.startswith((".cursor/rules/", ".claude/", ".github/instructions/"))
                    and path.suffix.lower() in {".md", ".mdc"})):
            key = rel.casefold()
            current = found.get(key)
            if current is None or _prefer_canonical_name(path, current):
                found[key] = path

    for directory, dirs, names in os.walk(root, followlinks=False, onerror=_discovery_error):
        descend = []
        for name in dirs:
            path = Path(directory) / name
            rel = path.relative_to(root).as_posix()
            # Only /** patterns prove every descendant is excluded. A literal
            # directory-name match alone must not change existing glob meaning.
            if name in SKIP_DIRS or any(
                pattern.endswith("/**") and fnmatch(rel, pattern[:-3]) for pattern in patterns
            ):
                continue
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                select(path)  # A link named AGENTS.md must not silently vanish.
                continue
            target = _repo_candidate(boundary, boundary, rel)
            if target != boundary / rel:
                select(path)
                continue
            descend.append(name)
        dirs[:] = descend
        for name in names:
            select(Path(directory) / name)
    selected = sorted(found.values(), key=lambda p: p.relative_to(root).as_posix())
    for path in selected:
        _scanner_source_target(boundary, path)
    return selected


def _discovery_error(exc: OSError) -> None:
    raise OSError(exc.errno, "Unable to discover instruction files") from exc


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    ascii_chars = sum(ord(c) < 128 for c in text)
    return max(1, round(ascii_chars / 4 + (len(text) - ascii_chars) / 1.7))


def _line(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _prohibited_markdown_table_example(
    text: str, index: int, command: str, context: _InstructionContext,
) -> bool:
    line_start = text.rfind("\n", 0, index) + 1
    line_end = text.find("\n", index)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end].strip()
    if context.inside_fence(index) or not line.startswith("|") or line.count("|") < 3:
        return False

    normalized_command = re.sub(r"\s+", " ", command.lower()).strip()
    number = context.line_index(index)
    for row in reversed(context.lines[max(0, number - 8):number]):
        candidate = text[row.start:row.end].strip()
        if row.kind in {"heading", "boundary", "code", "fence"}:
            break
        cleaned = re.sub(r"[`*_>#]", " ", candidate)
        cleaned = re.sub(r"\s+", " ", cleaned.lower()).strip()
        if DANGER_DOUBLE_NEGATIVE.search(cleaned):
            continue
        negation = DANGER_NEGATION.search(cleaned)
        if not negation or normalized_command not in cleaned:
            continue
        after_negation = cleaned[negation.end():]
        if DANGER_NEGATION_EXCEPTION.search(after_negation) is None:
            return True
    return False


def _dangerous_command_is_prohibited(
    text: str, index: int, command: str, context: _InstructionContext,
) -> bool:
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
    # A new affirmative action after a conjunction is a separate directive:
    # "Do not skip tests and then run rm -rf ..." does not prohibit rm.
    clause_prefix = re.split(
        r"\band\s+(?:then\s+)?(?:run|execute|use)\s+", clause_prefix, flags=re.I
    )[-1]
    if DANGER_DOUBLE_NEGATIVE.search(clause_prefix):
        return False
    negations = list(DANGER_NEGATION.finditer(clause_prefix))
    if not negations:
        return (
            context.command_is_prohibited(index)
            or _prohibited_markdown_table_example(text, index, command, context)
        )
    after_negation = clause_prefix[negations[-1].end():] + clause_suffix
    return DANGER_NEGATION_EXCEPTION.search(after_negation) is None


def _quoted_injection_example(text: str, index: int, command: str) -> bool:
    """Recognize only a complete, explicitly labeled, quoted attack example."""
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    line = text[start:end if end != -1 else len(text)].strip()
    # Do not exempt arbitrary quotes, code fences, or text following an example.
    # Requiring the entire line keeps an active trailing instruction visible.
    return re.fullmatch(
        r'(?:[-*]\s+)?(?:prompt[- ]injection|attack)\s+example:\s*'
        r'(?P<quote>[`\"\'])' + re.escape(command) + r'(?P=quote)\.?',
        line,
        re.I,
    ) is not None


def _active_prose_lines(context: _InstructionContext):
    """Source lines eligible for narrow prose rules, not a general intent parser."""
    for number, row in enumerate(context.lines, 1):
        if row.kind not in {"prose", "list"}:
            continue
        raw = context.text[row.start:row.end]
        if raw.startswith(("    ", "\t")) or raw.lstrip().startswith(">"):
            continue
        start = row.body_start if row.body_start is not None else row.start
        body = context.text[start:row.end].strip()
        # Quoted examples can contain sentence separators; do not split them
        # into seemingly active fragments. Literal-credential rules remain
        # independent of these conservative prose-only eligibility checks.
        if any(char in body for char in '`"\'“”‘’«»'):
            continue
        if context.command_is_prohibited(start):
            continue
        yield number, body


def _guardrail_policy_context(text: str) -> tuple[list[tuple[int, str]], bool]:
    """Bounded prose candidates for the opt-in review, not scored danger rules.

    Do not interpret HTML layouts at all. Explicit example headings exclude
    their section through the next equal/shallower heading. This intentionally
    declines ambiguous input rather than claiming to parse arbitrary Markdown.
    """
    if re.search(r"</?[A-Za-z]", text):
        return [], False
    context = _instruction_context(text)
    frontmatter = text.lstrip("\ufeff").startswith(("---\n", "---\r\n"))
    in_comment = False
    example_level = None
    candidates = []
    for number, row in enumerate(context.lines, 1):
        raw = text[row.start:row.end].rstrip("\r\n").lstrip("\ufeff")
        if frontmatter:
            if number > 1 and raw.strip() in {"---", "..."}:
                frontmatter = False
            continue
        if row.kind in {"code", "fence"}:
            continue
        if in_comment or "<!--" in raw:
            in_comment = raw.rfind("<!--") > raw.rfind("-->") if "-->" in raw else True
            continue
        if row.kind == "heading":
            atx = re.match(r"^ {0,3}(#{1,6})(?:\s|$)(.*)", raw)
            if atx:
                level = len(atx.group(1))
                title = re.sub(r"\s+#+\s*$", "", atx.group(2)).strip()
            elif number < len(context.lines):
                following = context.lines[number]
                underline = text[following.start:following.end].strip()
                if not re.fullmatch(r"=+|-+", underline):
                    continue
                level = 1 if underline.startswith("=") else 2
                title = raw.strip()
            else:
                continue
            if example_level is not None and level <= example_level:
                example_level = None
            title = re.sub(r"\*\*|__|`", "", title)
            if example_level is None and re.fullmatch(r"(?:Examples?|Samples?|示例|範例|范例|例子)[:：]?", title, re.I):
                example_level = level
            continue
        if example_level is not None:
            continue
        if row.kind not in {"prose", "list"} or raw.startswith(("    ", "\t")) or raw.lstrip().startswith(">"):
            continue
        start = row.body_start if row.body_start is not None else row.start
        body = text[start:row.end].strip().lstrip("\ufeff")
        if body.startswith(("`", '"', "'", "“", "‘")):
            continue
        body = re.sub(r"\*\*|__|`", "", body)
        if len(body) <= 512:
            candidates.append((number, body))
    return candidates, example_level is not None


def _deletion_guardrail_assessment(text: str) -> tuple[list[dict], list[dict], bool]:
    """Recognize finite constraints and opposing directives, not global safety."""
    english_approval = re.compile(
        r"(?:Before (?:deleting|removing) (?:existing |any |user )?files"
        r"(?:, overwriting user changes, or discarding uncommitted work)?, "
        r"(?:explain the exact targets and impact and )?(?:obtain explicit user approval|ask for (?:user )?confirmation)"
        r"|(?:Always )?ask for (?:user )?confirmation before (?:deleting|removing) (?:existing |any |user )?files)\.?",
        re.I,
    )
    english_ban = re.compile(
        r"(?:Never|Do not|Must not) (?:delete|remove) (?:existing |any |user )?files"
        r"(?: without (?:explicit user approval|user confirmation))?\.?", re.I,
    )
    chinese_approval = re.compile(
        r"(?:(?:删除|刪除)(?:现有文件|既有檔案|文件|檔案)?(?:前|之前)[，,]?"
        r"(?:必须|必須)(?:先)?(?:取得|获得|獲得|征得)(?:(?:用户|使用者)的?)?(?:明确|明確)?(?:确认|確認|授权|授權)"
        r"|在删除现有文件、覆盖用户改动或丢弃未提交的工作之前，必须先说明确切目标和影响范围，并取得用户的明确授权"
        r"|在刪除既有檔案、覆寫使用者變更或捨棄未提交的工作之前，必須先說明確切目標與影響範圍，並取得使用者的明確授權)[。.]?"
    )
    command = r"(?:rm(?:\s+-[A-Za-z]+)*|rmdir)"
    command_list = command + r"(?:(?:\s*,\s*(?:(?:or|and)\s+)?|\s+(?:or|and)\s+)" + command + r")*"
    command_ban = re.compile(
        r"(?:(?:Never|Do not|Must not) (?:use|run|execute)\s+|(?:禁止|不得|切勿)(?:执行|執行|使用)\s*)"
        + command_list + r"(?: under any circumstances)?[。. ]?", re.I,
    )
    files = r"(?:existing |any |user )?files"
    confirmation = r"(?:user )?confirmation"
    english_bypass = re.compile(
        r"(?:Before (?:deleting|removing) " + files + r", (?:do not|never) ask for " + confirmation
        + r"|(?:Do not|Never) ask for " + confirmation + r" before (?:deleting|removing) " + files
        + r"|(?:Always )?(?:delete|remove) " + files
        + r" without (?:asking for " + confirmation + r"|(?:explicit )?user approval|user confirmation))\.?", re.I,
    )
    chinese_bypass = re.compile(
        r"(?:删除|刪除)(?:现有文件|既有檔案|文件|檔案)?(?:前|之前)[，,]?"
        r"(?:不要|不得|无需|無需)(?:征求|徵求|取得|获得|獲得)"
        r"(?:用户|使用者)(?:的)?(?:明确|明確)?(?:确认|確認|授权|授權)[。.]?"
    )
    evidence = []
    signals = []
    candidates, open_example = _guardrail_policy_context(text)
    for number, body in candidates:
        kind = None
        if english_approval.fullmatch(body) or chinese_approval.fullmatch(body):
            kind = "approval_before_deletion"
        elif english_ban.fullmatch(body):
            kind = "file_deletion_constraint"
        elif command_ban.fullmatch(body):
            kind = "specific_command_ban"
        if kind is not None:
            evidence.append({"line": number, "kind": kind})
        if english_bypass.fullmatch(body) or chinese_bypass.fullmatch(body):
            signals.append({"line": number, "kind": "approval_bypass_directive"})
    return evidence, signals, open_example


def _deletion_guardrail_evidence(text: str) -> list[dict]:
    return _deletion_guardrail_assessment(text)[0]


def _false_success_lines(context: _InstructionContext):
    """Recognize bounded complete clauses without joining independent evidence."""
    for number, body in _active_prose_lines(context):
        # Unlike uploads, this grammar has no legitimate URL colon syntax.
        if ":" in body:
            continue
        body = re.sub(r"[*_]", "", body)
        for sentence in re.finditer(r"([^.!?;]+)([.!?;]|$)", body):
            if sentence.group(2) == "?":
                continue
            clause = sentence.group(1).strip()
            if len(clause) <= 512 and FALSE_SUCCESS_DIRECTIVE.fullmatch(clause):
                yield number
                break


def _network_upload_destination(destination: str) -> bool:
    """Recognize an explicit network sink without fetching or resolving it."""
    if UPLOAD_DESTINATION.fullmatch(destination):
        return True
    if re.search(r"\s", destination):
        return False
    try:
        url = urlsplit(destination)
        host = url.hostname
        # Accessing port also validates malformed or out-of-range ports.
        if url.scheme.lower() not in {"http", "https"} or not host or url.port == 0:
            return False
    except ValueError:
        return False
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True  # A literal hostname; no DNS lookup or trust claim.
    # Private network destinations are still transfers to another service.
    # An explicitly loopback/unspecified address is outside this narrow rule.
    mapped = getattr(address, "ipv4_mapped", None)
    address = mapped if mapped is not None else address
    return not (address.is_loopback or address.is_unspecified)


def _broad_environment_upload_lines(context: _InstructionContext):
    """Require an affirmative transfer, a bulk environment source, and a sink."""
    for number, body in _active_prose_lines(context):
        if re.match(r"(?:(?:attack|unsafe|bad|prompt[- ]injection)\s+)?example:\s*", body, re.I):
            continue
        # Preserve periods within URLs; unlike verification reporting, a
        # sentence break here needs following whitespace. Semicolons end a
        # clause so an earlier prohibition cannot hide a later transfer.
        for clause in re.split(r";|(?<=[.!?])\s+", body):
            clause = clause.strip()
            if len(clause) > 512 or clause.endswith("?"):
                continue
            separator = re.search(r"\s+to\s+", clause, re.I)
            if separator is not None:
                # Normalize source prose emphasis, never URL path/query data.
                clause = re.sub(r"[*_]", "", clause[:separator.start()]) + clause[separator.start():]
            match = BROAD_ENVIRONMENT_TRANSFER.fullmatch(clause.rstrip(".!"))
            if not match:
                continue
            destination = re.sub(
                r"\s+for\s+(?:diagnostics|troubleshooting|support|debugging|analysis)$",
                "", match.group("destination"), flags=re.I,
            )
            if _network_upload_destination(destination):
                yield number
                break


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


MARKDOWN_LINK = re.compile(r'!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s()]+))(?:\s+"[^"\n]*")?\s*\)')
MARKDOWN_REFERENCE = re.compile(r'!?\[([^\[\]\n]{0,999})\]\[([^\[\]\n]{0,999})\]')
REFERENCE_HEADER = re.compile(r' {0,3}\[([^\[\]\\\n]{1,999})\]:')
REFERENCE_DEFINITION = re.compile(
    r' {0,3}\[([^\[\]\\\n]{1,999})\]:[ \t]*'
    r'(?:<([^<>\\\n]*)>|([^\s<>\\()]+))'
    r'''(?:[ \t]+(?:"[^"\\\n]*"|'[^'\\\n]*'|\([^()\\\n]*\)))?[ \t]*'''
)
REFERENCE_HTML = re.compile(r'<!--|</?[A-Za-z][A-Za-z0-9:-]*(?:[ \t][^>\n]*)?/?>')
REFERENCE_CONTAINER = re.compile(
    r' {0,3}(?:>[ \t]*|(?:[-+*]|\d{1,9}[.)])[ \t]+)'
    r'.*?\[([^\[\]\\\n]{1,999})\]:'
)


def _markdown_span_index(spans: list[tuple[int, int]]) -> tuple[list[int], list[int]]:
    """Merge intervals once; membership must not rescan all document links."""
    starts: list[int] = []
    ends: list[int] = []
    for start, end in sorted(spans):
        if ends and start <= ends[-1]:
            ends[-1] = max(ends[-1], end)
        else:
            starts.append(start)
            ends.append(end)
    return starts, ends


def _markdown_span_overlaps(index: tuple[list[int], list[int]], start: int, end: int) -> bool:
    item = bisect_right(index[0], end - 1) - 1
    return item >= 0 and index[1][item] > start


def _markdown_escaped(text: str, index: int) -> bool:
    before = index
    while before and text[before - 1] == "\\":
        before -= 1
    return (index - before) % 2 == 1


def _markdown_code_spans(text: str, context: _InstructionContext) -> list[tuple[int, int]]:
    """Match equal backtick runs, including multiline spans, without an AST."""
    runs = [m for m in re.finditer(r'`+', text) if not context.inside_fence(m.start())]
    next_run: dict[int, int] = {}
    closers: dict[int, int] = {}
    for index in range(len(runs) - 1, -1, -1):
        length = len(runs[index].group())
        if length in next_run:
            closers[index] = next_run[length]
        next_run[length] = index
    spans = []
    index = 0
    while index < len(runs):
        closer = closers.get(index)
        if closer is not None and not _markdown_escaped(text, runs[index].start()):
            spans.append((runs[index].start(), runs[closer].end()))
            index = closer + 1
        else:
            index += 1
    return spans


def _markdown_reference_links(
    text: str, context: _InstructionContext,
) -> tuple[list[tuple[str, int]], list[tuple[int, int]]]:
    """Resolve only simple full/collapsed links to single-line definitions.

    Definitions are document-local and first-wins, including external targets.
    Unknown first definitions block guessing a later duplicate's destination.
    Return spans too so a definition/label is not reinterpreted as prose paths.
    HTML layouts, nested/escaped labels and shortcut links need manual review.
    """
    if ']:' not in text:
        return [], []
    if any(REFERENCE_HTML.search(raw) and not REFERENCE_DEFINITION.fullmatch(raw)
           for raw in text.splitlines()):
        return [], []
    code_spans = _markdown_code_spans(text, context)
    inline_spans = [m.span() for m in MARKDOWN_LINK.finditer(text)]
    code_index = _markdown_span_index(code_spans)
    inline_index = _markdown_span_index(inline_spans)
    literal_index = _markdown_span_index(code_spans + inline_spans)

    def label_key(label: str) -> str:
        return re.sub(r'[ \t\r\n]+', ' ', label.strip(' \t\r\n')).casefold()

    definitions: dict[str, tuple[str, int] | None] = {}
    spans: list[tuple[int, int]] = []
    can_define = True
    for number, row in enumerate(context.lines, 1):
        raw = text[row.start:row.end].rstrip('\r\n')
        if not raw.strip():
            can_define = True
            continue
        container = REFERENCE_CONTAINER.match(raw)
        if container and not context.inside_fence(row.start):
            # Containers are outside this parser. Do not let a later flat
            # duplicate replace their potentially earlier definition.
            definitions.setdefault(label_key(container.group(1)), None)
            can_define = False
            continue
        header = REFERENCE_HEADER.match(raw)
        if (can_define and header and not context.inside_fence(row.start)
                and not _markdown_span_overlaps(literal_index, row.start, row.end)):
            match = REFERENCE_DEFINITION.fullmatch(raw)
            key = label_key(header.group(1))
            if key and not key.startswith('^'):
                destination = (match.group(2) or match.group(3) or '') if match else None
                definitions.setdefault(key, (html.unescape(destination), number)
                                       if destination is not None else None)
                if match:
                    spans.append((row.start, row.end))
            can_define = match is not None
        else:
            # A reference definition cannot interrupt an ordinary paragraph.
            can_define = row.kind in {'heading', 'boundary', 'fence'}

    links = []
    definition_index = _markdown_span_index(spans)
    for match in MARKDOWN_REFERENCE.finditer(text):
        bracket = match.start() + (1 if match.group().startswith('!') else 0)
        if (context.inside_fence(match.start()) or _markdown_escaped(text, bracket)
                or _markdown_span_overlaps(code_index, bracket, bracket + 1)
                or _markdown_span_overlaps(code_index, match.end() - 1, match.end())
                or _markdown_span_overlaps(inline_index, match.start(), match.end())
                or _markdown_span_overlaps(definition_index, match.start(), match.end())):
            continue
        row = context.lines[context.line_index(match.start())]
        if text[row.start:row.end].startswith(('    ', '\t')):
            continue
        # Do not partially parse nested or escaped labels as a simpler link.
        if ('\\' in match.group() or (match.start() and text[match.start() - 1] == '[')
                or text[match.end():match.end() + 1] == ']'):
            continue
        key = label_key(match.group(2) or match.group(1))
        target = definitions.get(key)
        if target is not None:
            links.append(target)
            spans.append(match.span())
    return links, spans


def _local_markdown_links(
    text: str, context: _InstructionContext, reference_links: list[tuple[str, int]],
):
    """Extract local inline and supported reference destinations, never fetch."""
    links = list(reference_links)
    for match in MARKDOWN_LINK.finditer(text):
        if context.inside_fence(match.start()):
            continue
        destination = match.group(1) or match.group(2)
        links.append((destination, _line(text, match.start())))
    for destination, lineno in links:
        try:
            parts = urlsplit(destination)
        except ValueError:
            continue
        if parts.scheme or parts.netloc or not parts.path:
            continue
        candidate = unquote(parts.path)
        if candidate.startswith(("/", "\\", "~", "$")) or any(c in candidate for c in "*{}\x00"):
            continue
        yield candidate, lineno


def _non_required_path_reference(text: str, match: re.Match, value: str) -> bool:
    """Recognize narrow, same-line contexts; never exempt an entire line."""
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    if line_end == -1:
        line_end = len(text)
    before = text[max(line_start, match.start() - 256):match.start()]
    after = text[match.end():line_end]
    # An immediate, closed existence condition does not assert the file exists.
    # Do not infer optionality from distant words, an unclosed phrase or a link.
    if re.match(r"^[ \t]*\([ \t]*if[ \t]+(?:it[ \t]+)?exists[ \t]*"
                r"(?:\)|[-:][^()\r\n]{1,120}\))", after, re.I):
        return True
    # A two-component GitHub slug may look like a source path (owner/tool.js).
    # Require a repository/remote role, not merely 'GitHub' somewhere nearby.
    slug = r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+"
    if not re.fullmatch(slug, value):
        return False
    if re.match(r"^[ \t]+(?:repository|remote)(?:[ \t]+itself)?"
                r"[ \t]*(?:[.,;:!?)]|$)", after, re.I):
        return True
    if re.search(r"\b(?:merge target is|fork of|re-pushed to a branch in|"
                 r"CI trusts branches inside)[ \t]*$", before, re.I):
        return True
    # 'a fork of `owner/repo.js` and not `owner/repo.js` itself' refers to
    # the same slug twice. An unrelated local file in that sentence still counts.
    repeated = re.search(r"\bfork of[ \t]+`?(" + slug + r")`?[ \t]+and not[ \t]*$",
                         before, re.I)
    return bool(repeated and repeated.group(1) == value
                and re.match(r"^[ \t]+itself[ \t]*(?:[.,;:!?)]|$)", after, re.I))


def _candidate_paths(
    text: str, context: _InstructionContext, reference_spans: list[tuple[int, int]],
):
    link_spans = [match.span() for match in MARKDOWN_LINK.finditer(text)] + reference_spans
    link_index = _markdown_span_index(link_spans)
    for m in PATH_CANDIDATE.finditer(text):
        if _markdown_span_overlaps(link_index, m.start(), m.start() + 1):
            continue
        if context.inside_fence(m.start()):
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
        if _non_required_path_reference(text, m, value):
            continue
        yield value.replace("\\", "/"), _line(text, m.start())


def _repo_candidate(root: Path, base: Path, candidate: str) -> Path | None:
    # Never probe absolute, Windows drive-qualified, or escaping paths. The
    # scanner is about repository instructions, not the caller's filesystem.
    windows_candidate = PureWindowsPath(candidate)
    if Path(candidate).is_absolute() or windows_candidate.is_absolute() or windows_candidate.drive:
        return None
    try:
        target = (base / candidate).resolve(strict=False)
    except RuntimeError:  # pathlib symlink loops on Python 3.10-3.12
        return None
    except OSError as exc:
        if exc.errno == errno.ELOOP or getattr(exc, "winerror", None) == 1921:
            return None
        raise OSError(exc.errno, "Unable to resolve repository path") from exc
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
    candidate = candidate.replace("\\", "/")
    explicit_relative = candidate.startswith(("./", "../"))
    # Prose can describe commands run from the repository root rather than
    # from the instruction directory. Preserve that root interpretation. For a
    # nested AGENTS-family file, also accept a path relative to that file's
    # directory, which is the root of its instruction scope.
    bases = [root]
    if _is_agents_filename(source.name) and source.parent != root:
        # Instructions often use paths relative to a package root rather than
        # the exact directory containing a nested AGENTS.md. Accept any
        # in-repository ancestor interpretation to avoid false dead paths.
        current = source.parent
        while current != root:
            bases.append(current)
            current = current.parent
    elif explicit_relative and source.parent != root:
        # Explicit relative notation may also be document-relative in other
        # formats. Only these concrete bases count, not an arbitrary suffix.
        bases.append(source.parent)

    checked = False
    for base in bases:
        target = _repo_candidate(root, base, candidate)
        if target is None:
            continue
        checked = True
        if target.exists():
            return True
    if not checked:
        return None
    if not explicit_relative and repository_paths is not None:
        # lstrip('./') removes characters, not a path prefix: it previously
        # erased the significant dot in .github and dots in parent traversals.
        normalized = PurePosixPath(candidate).as_posix()
        if any(path == normalized or path.endswith("/" + normalized) for path in repository_paths):
            return True
    return False


def _path_index_error(exc: OSError) -> None:
    # A partial index is not evidence that a referenced path is missing. Keep
    # source-controlled path names and raw filesystem messages out of the CLI.
    raise OSError(exc.errno, "Unable to read repository path index") from exc


def _repository_path_index(root: Path) -> set[str]:
    root = root.resolve()
    paths: set[str] = set()
    # Prune dependency/admin trees before descent, and never follow directory
    # symlinks. This indexes names only; it does not read generated source files.
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=_path_index_error):
        descend = []
        for name in dirs:
            if name in PATH_INDEX_SKIP_DIRS:
                continue
            path = Path(directory) / name
            rel = path.relative_to(root).as_posix()
            target = _repo_candidate(root, root, rel)
            if target is None or not target.exists():
                continue
            paths.add(rel)
            # Resolved aliases include Windows junctions on versions where
            # is_symlink() alone would not stop traversal or directory loops.
            if target == path and not path.is_symlink():
                descend.append(name)
        dirs[:] = descend
        for name in files:
            path = Path(directory) / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                target = _repo_candidate(root, root, rel)
                if target is None or not target.exists():
                    continue
            paths.add(rel)
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
        and _is_agents_filename(left_path.name)
        and _is_agents_filename(right_path.name)
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
    report, _ = _analyze_with_texts(root, suppressions=suppressions)
    return report


def _analyze_with_texts(
    root: Path, *, suppressions: tuple[Suppression, ...] = (),
) -> tuple[Report, dict[str, str]]:
    """Keep scan-time text internal for comparisons; never attach it to Report."""
    tool = capture_tool_identity()
    root = root.resolve()
    files = discover(root)
    repository_paths = _repository_path_index(root)
    texts: dict[Path, str] = {}
    findings: list[Finding] = []
    total_tokens = 0

    for path in files:
        rel = path.relative_to(root).as_posix()
        text = _read_scanner_source(root, path)
        texts[path] = text
        context = _instruction_context(text)
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
                command = match.group(0).lstrip()
                # Some patterns include a leading whitespace boundary (sudo).
                # Locate the actual token, not the previous line's newline.
                index = match.end() - len(command)
                if pattern_rule.rule.code in PARSED_COMMAND_RULES:
                    risky, command = _command_options(
                        pattern_rule.rule.code, _command_words(text, index)
                    )
                    if not risky:
                        continue
                if (
                    pattern_rule.rule.code == "prompt-injection-override"
                    and _quoted_injection_example(text, match.start(), match.group(0))
                ):
                    continue
                if (
                    pattern_rule.rule.category == "danger"
                    and _dangerous_command_is_prohibited(text, index, command, context)
                ):
                    continue
                findings.append(_finding(pattern_rule.rule.code, rel, _line(text, index)))

        for lineno in _false_success_lines(context):
            findings.append(_finding("false-success-report", rel, lineno))
        for lineno in _broad_environment_upload_lines(context):
            findings.append(_finding("broad-environment-upload", rel, lineno))

        seen_refs: set[tuple[str, int]] = set()
        reference_links, reference_spans = _markdown_reference_links(text, context)
        for candidate, lineno in _local_markdown_links(text, context, reference_links):
            key = (candidate, lineno)
            if key in seen_refs:
                continue
            seen_refs.add(key)
            target = _repo_candidate(root, path.parent, candidate)
            if target is not None and not target.exists():
                findings.append(_finding("dead-path", rel, lineno, f"Referenced path does not exist: {candidate}"))
        for candidate, lineno in _candidate_paths(text, context, reference_spans):
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
    has_root_agents = any(
        len(PurePosixPath(rel).parts) == 1
        and PurePosixPath(rel).name.casefold() == "agents.md"
        for rel in rels
    )
    if len(files) >= 2 and not has_root_agents:
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
    report = Report(
        tool=tool,
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
    return report, {path.relative_to(root).as_posix(): text for path, text in texts.items()}


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
    tool_label = "Tool identity unavailable"
    if report.tool is not None:
        source = report.tool.source_sha256 or "unavailable"
        tool_label = f"Version {report.tool.version} · Tool source SHA-256 {source}"
    tool_label = html.escape(tool_label)
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
{suppressed_section}<h2>Files scanned</h2><ul>{file_rows}</ul><p class="muted">{tool_label}</p><p class="muted">Report fingerprint {fingerprint} · Generated by AgentConfigScore</p></main></body></html>'''
