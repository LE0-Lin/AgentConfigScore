from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Pattern


@dataclass(frozen=True)
class Rule:
    code: str
    severity: str
    category: str
    penalty: int
    summary: str
    description: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PatternRule:
    rule: Rule
    pattern: Pattern[str]


CATEGORY_CAPS = {
    "secret": 35,
    "danger": 35,
    "dead": 18,
    "size": 18,
    "quality": 30,
    "other": 15,
}

RULES = (
    Rule("curl-pipe-shell", "error", "danger", 18, "Remote script piped directly to a shell", "Flags persistent instructions that pipe curl output directly into sh or bash."),
    Rule("wget-pipe-shell", "error", "danger", 18, "Remote script piped directly to a shell", "Flags persistent instructions that pipe wget output directly into sh or bash."),
    Rule("rm-rf", "error", "danger", 10, "Destructive recursive deletion command", "Flags broad recursive force-deletion guidance in persistent agent instructions."),
    Rule("sudo", "warning", "danger", 6, "Privileged command in persistent agent instructions", "Flags instructions that encourage an agent to execute commands with elevated privileges."),
    Rule("chmod-777", "warning", "danger", 8, "World-writable permissions", "Flags instructions that make files or directories world-writable with chmod 777."),
    Rule("openai-key", "error", "secret", 25, "Possible OpenAI-style API key", "Flags strings shaped like common OpenAI-style API credentials."),
    Rule("github-token", "error", "secret", 25, "Possible GitHub token", "Flags strings shaped like common GitHub personal, OAuth, user, server, or refresh tokens."),
    Rule("aws-access-key", "error", "secret", 25, "Possible AWS access key", "Flags strings shaped like AWS access key IDs."),
    Rule("private-key", "error", "secret", 30, "Private key material detected", "Flags PEM/OpenSSH private-key headers in persistent agent instructions."),
    Rule("read-error", "warning", "other", 2, "Instruction file could not be read", "Reports a supported instruction file that could not be read during analysis."),
    Rule("context-too-large", "warning", "size", 12, "Persistent instruction context is very large", "Reports an instruction file estimated above 8,000 tokens."),
    Rule("context-large", "warning", "size", 6, "Persistent instruction context is large", "Reports an instruction file estimated above 5,000 tokens."),
    Rule("dead-path", "warning", "dead", 4, "Referenced repository path does not exist", "Flags repository-like paths referenced by agent instructions when the target path is absent."),
    Rule("high-duplication", "warning", "quality", 12, "High cross-file instruction duplication", "Reports when at least 35% of meaningful instruction lines are duplicated across files."),
    Rule("duplication", "warning", "quality", 7, "Cross-file instruction duplication", "Reports when at least 15% of meaningful instruction lines are duplicated across files."),
    Rule("contradiction", "error", "quality", 15, "Conflicting persistent directives", "Conservatively flags matching directive bodies that appear with both positive and negative polarity, excluding conflicts that are deterministically resolved by nested AGENTS.md scope precedence."),
    Rule("no-agents-md", "info", "quality", 3, "No canonical root AGENTS.md", "Reports multiple tool-specific instruction files without a root AGENTS.md to coordinate them."),
    Rule("no-config", "info", "other", 0, "No supported coding-agent instruction files found", "Reports that discovery found no supported coding-agent instruction files."),
)

RULES_BY_CODE = {rule.code: rule for rule in RULES}

if len(RULES_BY_CODE) != len(RULES):
    raise RuntimeError("AgentConfigScore rule IDs must be unique")

if any(rule.category not in CATEGORY_CAPS for rule in RULES):
    raise RuntimeError("Every AgentConfigScore rule must use a known scoring category")

if any(rule.severity not in {"error", "warning", "info"} for rule in RULES):
    raise RuntimeError("Every AgentConfigScore rule must use a known severity")


PATTERN_RULES = (
    PatternRule(RULES_BY_CODE["curl-pipe-shell"], re.compile(r"\bcurl\b[^\n|]{0,300}\|\s*(?:ba)?sh\b", re.I)),
    PatternRule(RULES_BY_CODE["wget-pipe-shell"], re.compile(r"\bwget\b[^\n|]{0,300}\|\s*(?:ba)?sh\b", re.I)),
    PatternRule(RULES_BY_CODE["rm-rf"], re.compile(r"\brm\s+-rf\b", re.I)),
    PatternRule(RULES_BY_CODE["sudo"], re.compile(r"(^|\s)sudo\s+", re.I | re.M)),
    PatternRule(RULES_BY_CODE["chmod-777"], re.compile(r"\bchmod\s+777\b", re.I)),
    PatternRule(RULES_BY_CODE["openai-key"], re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    PatternRule(RULES_BY_CODE["github-token"], re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    PatternRule(RULES_BY_CODE["aws-access-key"], re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    PatternRule(RULES_BY_CODE["private-key"], re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)


def get_rule(code: str) -> Rule | None:
    return RULES_BY_CODE.get(code)
