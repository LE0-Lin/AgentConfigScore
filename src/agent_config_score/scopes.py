"""Pure, bounded Cursor project-rule activation model; no I/O or scoring.

This predicts activation from declared file context, not an observed Cursor run.
Manual mentions, model selection, user/team rules and runtime settings are unknown.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import PurePosixPath, PureWindowsPath
import re


PROFILE = "cursor-file-context-v1"
MAX_TARGETS = 64
MAX_PATTERNS = 32
MAX_HEADER_LINES = 128
MAX_PATTERN_LENGTH = 256


class ScopeInputError(ValueError):
    """The declared context cannot be analyzed by the bounded profile."""


def normalize_targets(values: list[str]) -> tuple[str, ...]:
    if not values or len(values) > MAX_TARGETS:
        raise ScopeInputError("scope requires 1 to 64 declared target paths")
    targets = set()
    for value in values:
        if not isinstance(value, str) or not value or len(value) > 1024:
            raise ScopeInputError("scope target must be a nonempty bounded relative file path")
        path = PurePosixPath(value.replace("\\", "/"))
        if (path.is_absolute() or PureWindowsPath(value).drive or ".." in path.parts
                or not path.parts or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise ScopeInputError("scope targets must remain repository-relative; absolute/parent/control paths are unsupported")
        targets.add(path.as_posix())
    return tuple(sorted(targets))


def _component_matches(pattern: str, value: str) -> bool:
    if "*" not in pattern:
        return pattern == value
    # Wildcard dynamic programming, not a potentially backtracking regex.
    previous = [True] + [False] * len(value)
    for char in pattern:
        current = [previous[0] if char == "*" else False] + [False] * len(value)
        for index, candidate in enumerate(value, 1):
            current[index] = (previous[index] or current[index - 1]) if char == "*" else (
                previous[index - 1] and char == candidate)
        previous = current
    return previous[-1]


@dataclass(frozen=True)
class ScopeGlob:
    segments: tuple[str, ...]

    @classmethod
    def parse(cls, value: str) -> ScopeGlob:
        if (not value or len(value) > MAX_PATTERN_LENGTH or "\\" in value
                or any(c in value for c in "?[]{}!(),\"'`")
                or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise ScopeInputError("unsupported glob grammar")
        path = PurePosixPath(value)
        segments = value.split("/")
        if (path.is_absolute() or PureWindowsPath(value).drive
                or any(part in {"", ".", ".."} for part in segments)
                or any("**" in part and part != "**" for part in segments)):
            raise ScopeInputError("unsupported glob path")
        # A terminal ** denotes files below that prefix, not the prefix itself.
        if segments[-1] == "**":
            segments.append("*")
        return cls(tuple(segments))

    def matches(self, target: str) -> bool:
        def closure(states):
            result = set(states)
            for index in range(len(self.segments)):
                if index in result and self.segments[index] == "**":
                    result.add(index + 1)
            return result

        states = closure({0})
        for component in target.split("/"):
            following = set()
            for index in states:
                if index == len(self.segments):
                    continue
                pattern = self.segments[index]
                if pattern == "**":
                    following.add(index)
                elif _component_matches(pattern, component):
                    following.add(index + 1)
            states = closure(following)
            if not states:
                return False
        return len(self.segments) in states


@dataclass(frozen=True)
class CursorRuleModel:
    file: str
    mode: str
    reason: str
    patterns: tuple[ScopeGlob, ...] = ()
    metadata_lines: tuple[tuple[str, int], ...] = ()
    body_line: int | None = 1

    def activate(self, targets: tuple[str, ...]) -> dict:
        matched = ()
        state = "unknown"
        reason = self.reason
        if self.mode == "always":
            state, matched = "active", targets
        elif self.mode == "patterns":
            matched = tuple(target for target in targets if any(pattern.matches(target) for pattern in self.patterns))
            state = "active" if matched else "inactive"
            reason = "declared_target_matches" if matched else "no_declared_target_matches"
        elif self.mode == "ignored":
            state = "inactive"
        # Do not export raw descriptions, glob values or instruction contents.
        return {"file": self.file, "mode": self.mode, "activation": state,
                "reason": reason, "pattern_count": len(self.patterns),
                "metadata_lines": dict(self.metadata_lines), "body_line": self.body_line,
                "matched_targets": list(matched)}


def _scalar(value: str) -> str:
    value = value.strip()
    if not value or value.startswith("#"):
        return ""
    if value.startswith('"'):
        result, end = json.JSONDecoder().raw_decode(value)
        if not isinstance(result, str):
            raise ValueError("not a string")
        remainder = value[end:].strip()
        if remainder and not remainder.startswith("#"):
            raise ValueError("trailing metadata")
        return result
    if value.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", value)
        if match is None:
            raise ValueError("unsupported quoted scalar")
        return match.group(1).replace("''", "'")
    value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
    if (not value or value[0] in "[{&*!|>@`" or ": " in value
            or value.lower() in {"~", "null", "true", "false", "yes", "no", "on", "off", ".nan", ".inf", "-.inf"}
            or re.match(r"[+-]?(?:[0-9]|\.[0-9])", value)
            or (value[0] in "-?:" and (len(value) == 1 or value[1].isspace()))):
        raise ValueError("unsupported scalar")
    return value


def parse_cursor_rule(file: str, text: str) -> CursorRuleModel:
    """Recognize only scalar metadata; unsupported YAML stays explicitly unknown."""
    if not file.startswith(".cursor/rules/"):
        return CursorRuleModel(file, "unknown", "outside_root_cursor_rules", body_line=None)
    if PurePosixPath(file).suffix == ".md":
        return CursorRuleModel(file, "ignored", "plain_md_not_project_rule", body_line=None)
    if PurePosixPath(file).suffix != ".mdc":
        return CursorRuleModel(file, "unknown", "extension_case_or_format_unmodelled", body_line=None)
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return CursorRuleModel(file, "unknown", "frontmatter_missing")
    closing = next((index for index, line in enumerate(lines[1:MAX_HEADER_LINES + 1], 1)
                    if line.strip() == "---"), None)
    if closing is None:
        return CursorRuleModel(file, "unknown", "frontmatter_unclosed_or_over_limit", body_line=None)
    body_line = closing + 2
    fields = {}
    origins = []
    try:
        for number, line in enumerate(lines[1:closing], 2):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.fullmatch(r"(description|globs|alwaysApply):(?:[ \t]+(.*)|[ \t]*)", line)
            if match is None or match[1] in fields:
                raise ValueError("unsupported or duplicate metadata")
            fields[match[1]] = (match[2] or "").strip()
            origins.append((match[1], number))
        flag = re.split(r"\s+#", fields.get("alwaysApply", ""), maxsplit=1)[0].strip()
        # Validate scalar syntax even for fields semantically ignored by Always.
        description = _scalar(fields.get("description", ""))
        globs = _scalar(fields.get("globs", ""))
        description.encode("utf-8")
        globs.encode("utf-8")
        if flag not in {"true", "false"}:
            raise ValueError("missing or nonboolean flag")
        if flag == "true":
            return CursorRuleModel(file, "always", "always_apply", metadata_lines=tuple(origins), body_line=body_line)
        if globs:
            patterns = [part.strip() for part in globs.split(",")]
            if len(patterns) > MAX_PATTERNS:
                raise ValueError("pattern limit")
            parsed = tuple(ScopeGlob.parse(part) for part in patterns)
            return CursorRuleModel(file, "patterns", "file_patterns", parsed, tuple(origins), body_line)
        mode = "agent_selected" if description else "manual"
        reason = "model_selection_not_observed" if description else "manual_mentions_not_observed"
        return CursorRuleModel(file, mode, reason, metadata_lines=tuple(origins), body_line=body_line)
    except (ValueError, RecursionError):
        return CursorRuleModel(file, "unknown", "metadata_or_glob_outside_profile",
                               metadata_lines=tuple(origins), body_line=body_line)
