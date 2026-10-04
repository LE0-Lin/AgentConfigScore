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
    "coverage": 30,
    "other": 15,
}

RULES = (
    Rule("curl-pipe-shell", "error", "danger", 18, "Remote script piped directly to a shell", "Flags persistent instructions that pipe curl output directly into sh or bash."),
    Rule("wget-pipe-shell", "error", "danger", 18, "Remote script piped directly to a shell", "Flags persistent instructions that pipe wget output directly into sh or bash."),
    Rule("rm-rf", "error", "danger", 10, "Destructive recursive deletion command", "Flags rm commands combining recursive and force options, including reordered, split, and long options. A later interactive option overrides force."),
    Rule("sudo", "warning", "danger", 6, "Privileged command in persistent agent instructions", "Flags instructions that encourage an agent to execute commands with elevated privileges."),
    Rule("chmod-777", "warning", "danger", 8, "World-writable permissions", "Flags instructions that make files or directories world-writable with chmod 777."),
    Rule("powershell-download-exec", "error", "danger", 18, "Remote PowerShell content executed directly", "Flags persistent instructions that pipe Invoke-WebRequest output directly into Invoke-Expression."),
    Rule("git-clean-force", "error", "danger", 12, "Forced Git cleanup removes untracked files", "Flags git clean commands combining force and directory removal options, excluding dry-run and interactive modes."),
    Rule("docker-system-prune", "error", "danger", 12, "Aggressive Docker system cleanup", "Flags docker system prune commands combining all and force options; filter values and later commands are not interpreted as options."),
    Rule("kubectl-delete-namespace", "error", "danger", 15, "Kubernetes namespace deletion", "Flags persistent instructions that delete an entire Kubernetes namespace."),
    Rule("prompt-injection-override", "warning", "danger", 8, "Instruction attempts to override prior instructions", "Flags explicit directives such as 'ignore previous instructions' or 'disregard prior instructions' in persistent agent configuration. This deliberately narrow heuristic targets a common prompt-injection primitive without attempting semantic prompt-injection detection."),
    Rule("false-success-report", "error", "quality", 12, "Instruction requires misleading verification reporting", "Flags narrowly recognized English prose directives to ignore errors and report success, or to claim tests passed despite failure or without running them. Prohibitions, quotations, code examples, and merely skipping tests are not sufficient evidence. This is a review signal, not general semantic verification."),
    Rule("broad-environment-upload", "warning", "danger", 12, "Instruction sends the full environment to a network service", "Flags narrowly recognized English prose directives combining a transfer action, all environment variables or the full process environment, and an explicit HTTP(S) or named network destination. This is a potential credential-exposure review signal, not proof of malicious intent or actual transmission. Limited/redacted data, names-only reports, prohibitions, examples, and literal loopback destinations are outside the grammar."),
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
    Rule("contradiction", "error", "quality", 15, "Conflicting persistent directives", "Conservatively flags matching directive bodies that appear with both positive and negative polarity, excluding conflicts deterministically resolved by AGENTS.md directory scope or Codex AGENTS.override.md precedence."),
    Rule("no-agents-md", "info", "quality", 3, "No canonical root AGENTS.md", "Reports multiple tool-specific instruction files without a root AGENTS.md to coordinate them."),
    Rule("empty-instructions", "error", "coverage", 30, "Instruction file is empty", "Reports supported coding-agent instruction files that contain no instructions and therefore cannot be meaningfully audited."),
    Rule("no-config", "error", "coverage", 30, "No supported coding-agent instruction files found", "Reports that discovery found no supported coding-agent instruction files, so an A-grade audit result would be misleading."),
    Rule("instruction-file-removed", "error", "coverage", 0, "Instruction file removed in candidate", "Regression-only rule that reports removal of a supported instruction file unless its exact content moved to another supported file."),
    Rule("directive-polarity-flip", "error", "quality", 0, "Persistent directive reversed in candidate", "Regression-only rule that reports an exact directive changing between positive and negative polarity in the same instruction file."),
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
    PatternRule(RULES_BY_CODE["rm-rf"], re.compile(r"\brm(?=[ \t])", re.I)),
    PatternRule(RULES_BY_CODE["sudo"], re.compile(r"(^|\s)sudo\s+", re.I | re.M)),
    PatternRule(RULES_BY_CODE["chmod-777"], re.compile(r"\bchmod\s+777\b", re.I)),
    PatternRule(RULES_BY_CODE["powershell-download-exec"], re.compile(r"\b(?:Invoke-WebRequest|iwr)\b[^\n|]{0,300}\|\s*(?:Invoke-Expression|iex)\b", re.I)),
    PatternRule(RULES_BY_CODE["git-clean-force"], re.compile(r"\bgit[ \t]+clean(?=[ \t])", re.I)),
    PatternRule(RULES_BY_CODE["docker-system-prune"], re.compile(r"\bdocker[ \t]+system[ \t]+prune(?=[ \t])", re.I)),
    PatternRule(RULES_BY_CODE["kubectl-delete-namespace"], re.compile(r"\bkubectl\s+delete\s+(?:namespace|namespaces|ns)\b", re.I)),
    PatternRule(RULES_BY_CODE["prompt-injection-override"], re.compile(r"\b(?:ignore|disregard)\s+(?:(?:all|any|the)\s+)?(?:previous|prior|earlier)\s+(?:instructions?|directives?|rules?)\b", re.I)),
    PatternRule(RULES_BY_CODE["openai-key"], re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    PatternRule(RULES_BY_CODE["github-token"], re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    PatternRule(RULES_BY_CODE["aws-access-key"], re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    PatternRule(RULES_BY_CODE["private-key"], re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)


def get_rule(code: str) -> Rule | None:
    return RULES_BY_CODE.get(code)
