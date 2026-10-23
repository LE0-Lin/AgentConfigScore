"""Opt-in, unscored deletion-policy review and confirmed append-only suggestions."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat

from .provenance import ToolIdentity, capture_tool_identity
from .scanner import _deletion_guardrail_evidence, _instruction_context, _scanner_source_target, discover


class GuardrailError(ValueError):
    pass


TEMPLATES = {
    "en": (
        "## Deletion and overwrite safeguards\n\n"
        "- Before deleting existing files, overwriting user changes, or discarding uncommitted work, "
        "explain the exact targets and impact and obtain explicit user approval.\n"
        "- This instruction does not authorize destructive commands; follow any stricter repository rules.\n"
    ),
    "simplified": (
        "## 删除与覆盖保护\n\n"
        "- 在删除现有文件、覆盖用户改动或丢弃未提交的工作之前，必须先说明确切目标和影响范围，并取得用户的明确授权。\n"
        "- 这段指令不授权执行破坏性命令；仓库中更严格的规则仍然适用。\n"
    ),
    "traditional": (
        "## 刪除與覆寫保護\n\n"
        "- 在刪除既有檔案、覆寫使用者變更或捨棄未提交的工作之前，必須先說明確切目標與影響範圍，並取得使用者的明確授權。\n"
        "- 這段指令不授權執行破壞性命令；儲存庫中更嚴格的規則仍然適用。\n"
    ),
}
MAX_SOURCE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class GuardrailReview:
    file: str
    status: str
    evidence: tuple[dict, ...]
    proposed_append: str
    confirmation_token: str | None
    manual_review_reasons: tuple[str, ...]
    tool: ToolIdentity
    applied: bool = False

    def to_dict(self) -> dict:
        return {
            "schema_version": 1, "tool": self.tool.to_dict(), "file": self.file, "check": "deletion-safeguards",
            "status": self.status, "advisory_only": True, "score_affected": False,
            "scope": "selected_file_only", "evidence": list(self.evidence),
            "proposed_append": self.proposed_append, "confirmation_token": self.confirmation_token,
            "manual_review_reasons": list(self.manual_review_reasons), "applied": self.applied,
        }


def _relative_file(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (not normalized or path.is_absolute() or PureWindowsPath(normalized).drive
            or ".." in path.parts or "\x00" in normalized or path.as_posix() == "."):
        raise GuardrailError("--file must be a repository-relative supported instruction filename")
    return path.as_posix()


def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _manual_reasons(path: Path, target: Path, text: str, info: os.stat_result) -> tuple[str, ...]:
    reasons = []
    if path != target or path.is_symlink():
        reasons.append("file_alias")
    if info.st_nlink != 1:
        reasons.append("shared_or_unknown_link_count")
    if info.st_ino == 0:
        reasons.append("unknown_file_identity")
    context = _instruction_context(text)
    if sum(row.kind == "fence" for row in context.lines) % 2:
        reasons.append("unclosed_code_fence")
    if re.search(r"<[/!A-Za-z]", text):
        reasons.append("html_or_comment_markup")
    if text.startswith("---\n") and not re.search(r"(?m)^(?:---|\.\.\.)\s*$", text[4:]):
        reasons.append("unclosed_frontmatter")
    return tuple(reasons)


def _append_bytes(original: bytes, block: str) -> bytes:
    remainder = original.replace(b"\r\n", b"")
    newline = "\r\n" if b"\r\n" in original and b"\n" not in remainder and b"\r" not in remainder else "\n"
    separator = newline if original.endswith((b"\n", b"\r")) else newline * 2
    if not original:
        separator = ""
    return (separator + block.replace("\n", newline)).encode("utf-8")


def _confirmation(root: Path, rel: str, original: bytes, info: os.stat_result, addition: bytes) -> str:
    payload = {
        "format": "acs-guardrail-append-v1", "root": str(root), "file": rel,
        "identity": _identity(info), "source": hashlib.sha256(original).hexdigest(),
        "addition": hashlib.sha256(addition).hexdigest(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _read_source(root: Path, path: Path, target: Path) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(target, flags)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or _scanner_source_target(root, path) != target
                or _identity(target.stat()) != _identity(info)):
            raise GuardrailError("Selected source changed while opening; preview again")
        if info.st_size > MAX_SOURCE_BYTES:
            raise GuardrailError("Guardrail review is limited to 1 MiB instruction files")
        original = source.read(MAX_SOURCE_BYTES + 1)
        if len(original) > MAX_SOURCE_BYTES or _identity(os.fstat(source.fileno())) != _identity(info):
            raise GuardrailError("Selected source changed while reading; preview again")
    return original, info


def _apply_append(root: Path, path: Path, expected: bytes, info: os.stat_result, addition: bytes) -> None:
    # Never replace/truncate the original. Recheck the opened object as well as
    # the pathname. This is not atomic against arbitrary concurrent writers.
    if _scanner_source_target(root, path) != path or path.is_symlink() or path.stat().st_nlink != 1:
        raise GuardrailError("Target changed or became an alias; preview again")
    flags = os.O_RDWR | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or opened.st_ino == 0 or _identity(opened) != _identity(info):
            raise GuardrailError("Target identity changed; preview again")
        with os.fdopen(os.dup(descriptor), "rb") as source:
            current = source.read(MAX_SOURCE_BYTES + 1)
        if (current != expected or _identity(path.stat()) != _identity(info)
                or _identity(os.fstat(descriptor)) != _identity(info)
                or _scanner_source_target(root, path) != path or path.is_symlink()):
            raise GuardrailError("Target contents or path changed; preview again")
        if os.write(descriptor, addition) != len(addition):
            raise GuardrailError("Append was incomplete; inspect the file before retrying")
    finally:
        os.close(descriptor)


def review_guardrails(root: Path, *, file: str = "AGENTS.md", template_language: str = "en", apply: str | None = None) -> GuardrailReview:
    if template_language not in TEMPLATES:
        raise GuardrailError("Unsupported template language")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise GuardrailError("Repository path must be a directory")
    rel = _relative_file(file)
    path = root / rel
    if path not in discover(root):
        raise GuardrailError("Selected file was not discovered: choose an existing, non-ignored supported instruction file with --file")
    target = _scanner_source_target(root, path)
    try:
        original, info = _read_source(root, path, target)
        text = original.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        evidence = tuple(_deletion_guardrail_evidence(text))
        tool = capture_tool_identity()
        if evidence:
            return GuardrailReview(rel, "recognized", evidence, "", None, (), tool)
        reasons = _manual_reasons(path, target, text, info)
        block = TEMPLATES[template_language]
        addition = _append_bytes(original, block)
        token = None if reasons else _confirmation(root, rel, original, info, addition)
        if apply is not None:
            if token is None:
                raise GuardrailError("Automatic append is unavailable for this source; review and merge the suggestion manually")
            if not re.fullmatch(r"[0-9a-f]{64}", apply) or not hmac.compare_digest(token, apply):
                raise GuardrailError("Confirmation does not match this file and proposal; preview again")
            _apply_append(root, path, original, info, addition)
        return GuardrailReview(rel, "appended" if apply is not None else "review_needed", (), block, token, reasons, tool, applied=apply is not None)
    except UnicodeError as exc:
        raise GuardrailError("Guardrail suggestions require a UTF-8 instruction file") from exc
    except OSError as exc:
        raise GuardrailError("Unable to read or append selected source; inspect the file before retrying") from exc
