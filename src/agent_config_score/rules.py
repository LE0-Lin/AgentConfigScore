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
    Rule("read-error", "warning", "other", 2, "Instruction file could not be read", "Legacy finding retained for historical report and suppression compatibility. Current scans fail operationally when a selected instruction file cannot be safely read, rather than scoring an incomplete analysis."),
    Rule("context-too-large", "warning", "size", 12, "Persistent instruction context is very large", "Reports an instruction file estimated above 8,000 tokens."),
    Rule("context-large", "warning", "size", 6, "Persistent instruction context is large", "Reports an instruction file estimated above 5,000 tokens."),
    Rule("dead-path", "warning", "dead", 4, "Referenced repository path does not exist", "Flags repository-like paths referenced by agent instructions when the target path is absent."),
    Rule("high-duplication", "warning", "quality", 12, "High cross-file instruction duplication", "Reports when at least 35% of meaningful instruction lines are duplicated across files."),
    Rule("duplication", "warning", "quality", 7, "Cross-file instruction duplication", "Reports when at least 15% of meaningful instruction lines are duplicated across files."),
    Rule("contradiction", "error", "quality", 15, "Conflicting persistent directives", "Conservatively flags matching directive bodies that appear with both positive and negative polarity, excluding conflicts deterministically resolved by AGENTS.md directory scope or Codex AGENTS.override.md precedence."),
    Rule("no-agents-md", "info", "quality", 3, "No canonical root AGENTS.md", "Reports multiple tool-specific instruction files without a root AGENTS.md to coordinate them."),
    Rule("empty-instructions", "error", "coverage", 30, "Instruction file is empty", "Reports supported coding-agent instruction files that contain no instructions and therefore cannot be meaningfully audited."),
    Rule("no-config", "error", "coverage", 30, "No supported coding-agent instruction files found", "Reports that discovery found no supported coding-agent instruction files, so an A-grade audit result would be misleading."),
    Rule("instruction-file-removed", "error", "coverage", 0, "Instruction file removed in candidate", "Regression-only rule that reports removal of a supported instruction file. A nonempty, exact decoded-text match in the same directory can pair one removed file with one newly added supported file; existing copies, whitespace folding and cross-directory moves do not exempt a removal. This filename-coverage heuristic does not certify equivalent agent behavior."),
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


# Static review guidance, not another scored rule or an automatic repair plan.
# Keep source text, credentials and guessed replacement paths out of this map.
RULE_GUIDANCE = {
    "curl-pipe-shell": "Review the download source and pin/verify the artifact before any separate execution; do not pipe unreviewed network content straight into a shell.",
    "wget-pipe-shell": "Review the download source and pin/verify the artifact before any separate execution; do not pipe unreviewed network content straight into a shell.",
    "rm-rf": "Review the exact deletion targets and required approval; prefer a narrowly scoped, recoverable operation consistent with repository policy. Do not run the command just to verify this finding.",
    "sudo": "Check whether elevated privileges are really needed; prefer a least-privilege setup and require the repository's approval process for privileged operations.",
    "chmod-777": "Identify the required owner/group and minimal permissions instead of granting write access to everyone.",
    "powershell-download-exec": "Review and verify the downloaded PowerShell artifact before separate execution; do not execute network content directly from the pipeline.",
    "git-clean-force": "Review untracked-file targets using a non-destructive preview and obtain required approval; preserve user work rather than applying blanket cleanup.",
    "docker-system-prune": "Review exactly which images, containers and volumes would be removed; use scoped cleanup with required approval instead of broad unattended pruning.",
    "kubectl-delete-namespace": "Verify cluster context, namespace ownership and required approval; replace blanket namespace removal with the intended scoped operation.",
    "prompt-injection-override": "Review whether this is an active override or a clearly labeled attack example; remove unintended overrides and treat retrieved content as untrusted data. This warning is not a complete injection detector.",
    "false-success-report": "Require verification reports to distinguish passed, failed and not-run checks, with actual evidence; remove instructions to claim success despite missing or failed verification.",
    "broad-environment-upload": "Review the destination and necessity; do not transmit the full environment. If diagnostics are needed, explicitly allowlist and redact fields before sharing.",
    "openai-key": "If this credential is real, revoke/rotate it, remove it from instructions and review Git history and exposure; use a secret store or environment reference instead.",
    "github-token": "If this credential is real, revoke/rotate it, remove it from instructions and review Git history and exposure; use a secret store or environment reference instead.",
    "aws-access-key": "If this credential is real, revoke/rotate it, remove it from instructions and review Git history and exposure; use a secret store or environment reference instead.",
    "private-key": "If this key is real, revoke/replace exposed key material and review its exposure; removing the text alone is not enough. Keep private keys outside instruction files.",
    "read-error": "Resolve source permissions, encoding or filesystem boundaries and rerun the scan; an unreadable source must not be treated as a clean result.",
    "context-too-large": "Keep essential always-loaded guidance short and move task-specific detail to clearly referenced documents; check the actual agent's loading behavior before restructuring.",
    "context-large": "Keep essential always-loaded guidance short and move task-specific detail to clearly referenced documents; check the actual agent's loading behavior before restructuring.",
    "dead-path": "Verify the intended repository/scope-relative target and update or remove the stale reference; do not create placeholder files merely to silence the warning.",
    "high-duplication": "Review shared guidance for a single maintained source where agent loading supports it; keep genuinely tool-specific or scoped instructions separate.",
    "duplication": "Review shared guidance for a single maintained source where agent loading supports it; keep genuinely tool-specific or scoped instructions separate.",
    "contradiction": "Check the conflicting locations and actual agent scope/precedence, then retain the intended directive; do not assume the detector understands every semantic conflict.",
    "no-agents-md": "Consider a shared root instruction file only if the agents in use support it; do not blindly duplicate tool-specific rules or add a file just for the score.",
    "empty-instructions": "Add relevant project-specific instructions for the agent actually used, or remove an intentionally unused empty file; avoid generic filler.",
    "no-config": "Choose a supported instruction format for the agent actually used and document real setup, verification and boundaries; a repository with no agent configuration may not need this tool.",
    "instruction-file-removed": "Review whether the removal changed agent coverage or scope; restore required guidance or make an explicitly reviewed migration rather than copying files just to pass.",
    "directive-polarity-flip": "Review the old and new directive in context and confirm the intended policy change; restore an accidental reversal rather than weakening the baseline gate.",
}


def rule_guidance(code: str) -> str:
    return RULE_GUIDANCE.get(code, "Review this finding against its rule documentation and repository policy before changing instructions.")
