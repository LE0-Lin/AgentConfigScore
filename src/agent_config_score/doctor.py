from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from .config import CONFIG_NAME, SCHEMA_URL, ConfigError, load_policy
from .gitdiff import GitError, detect_base_ref, repository_root
from .scanner import discover


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DoctorReport:
    root: str
    checks: tuple[DoctorCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.status != "error" for check in self.checks)

    @property
    def warnings(self) -> int:
        return sum(check.status == "warning" for check in self.checks)

    @property
    def errors(self) -> int:
        return sum(check.status == "error" for check in self.checks)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "ok": self.ok,
            "warnings": self.warnings,
            "errors": self.errors,
            "checks": [check.to_dict() for check in self.checks],
        }


def _check_config(root: Path) -> tuple[list[DoctorCheck], object | None]:
    checks: list[DoctorCheck] = []
    path = root / CONFIG_NAME
    if not path.exists():
        checks.append(DoctorCheck(
            "config",
            "warning",
            f"{CONFIG_NAME} is missing; compatibility defaults will be used.",
        ))
        return checks, None
    if not path.is_file():
        checks.append(DoctorCheck("config", "error", f"{CONFIG_NAME} exists but is not a file."))
        return checks, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        policy = load_policy(root)
    except (OSError, json.JSONDecodeError, ConfigError) as exc:
        checks.append(DoctorCheck("config", "error", f"Invalid {CONFIG_NAME}: {exc}"))
        return checks, None

    checks.append(DoctorCheck(
        "config",
        "pass",
        f"{CONFIG_NAME} is valid (max_drop={policy.max_drop}, fail_on_new_errors={str(policy.fail_on_new_errors).lower()}).",
    ))

    schema = raw.get("$schema") if isinstance(raw, dict) else None
    if schema == SCHEMA_URL:
        checks.append(DoctorCheck("schema", "pass", "Configuration uses the canonical AgentConfigScore JSON Schema."))
    elif schema is None:
        checks.append(DoctorCheck(
            "schema",
            "warning",
            f"No $schema entry; add {SCHEMA_URL} for editor validation.",
        ))
    else:
        checks.append(DoctorCheck(
            "schema",
            "warning",
            f"$schema points to a non-canonical URI: {schema}",
        ))

    today = datetime.now(timezone.utc).date()
    soon = [item for item in policy.suppressions if 0 <= (item.expires - today).days <= 30]
    if soon:
        detail = ", ".join(f"{item.rule} ({item.expires.isoformat()})" for item in soon)
        checks.append(DoctorCheck("suppressions", "warning", f"Suppression expiry within 30 days: {detail}"))
    else:
        checks.append(DoctorCheck(
            "suppressions",
            "pass",
            f"{len(policy.suppressions)} active suppression(s); none expire within 30 days.",
        ))
    return checks, policy


def _check_workflow(root: Path) -> DoctorCheck:
    path = root / ".github" / "workflows" / "agent-config-score.yml"
    if not path.exists():
        return DoctorCheck(
            "workflow",
            "warning",
            "Standard .github/workflows/agent-config-score.yml is missing; CI integration may be custom or absent.",
        )
    if not path.is_file():
        return DoctorCheck("workflow", "error", "AgentConfigScore workflow path exists but is not a file.")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return DoctorCheck("workflow", "error", f"Could not read AgentConfigScore workflow: {exc}")

    if "LE0-Lin/AgentConfigScore@" not in text:
        return DoctorCheck(
            "workflow",
            "error",
            "Standard AgentConfigScore workflow does not invoke LE0-Lin/AgentConfigScore@...",
        )
    if "fetch-depth: 0" not in text:
        return DoctorCheck(
            "workflow",
            "warning",
            "AgentConfigScore workflow is present, but actions/checkout is not configured with fetch-depth: 0.",
        )
    return DoctorCheck("workflow", "pass", "GitHub Actions regression workflow is installed with full Git history.")


def diagnose(root: Path) -> DoctorReport:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        return DoctorReport(str(root), (DoctorCheck("repository", "error", f"Not a directory: {root}"),))

    checks, _policy = _check_config(root)

    files = discover(root)
    if files:
        checks.append(DoctorCheck(
            "instructions",
            "pass",
            f"Discovered {len(files)} supported instruction file(s): "
            + ", ".join(path.relative_to(root).as_posix() for path in files[:5])
            + (" ..." if len(files) > 5 else ""),
        ))
    else:
        checks.append(DoctorCheck(
            "instructions",
            "warning",
            "No supported coding-agent instruction files were discovered.",
        ))

    try:
        git_root = repository_root(root)
    except GitError as exc:
        checks.append(DoctorCheck("git", "warning", f"Git-native diff is unavailable: {exc}"))
    else:
        checks.append(DoctorCheck("git", "pass", f"Git repository detected at {git_root}."))
        try:
            base_ref = detect_base_ref(git_root)
        except GitError as exc:
            checks.append(DoctorCheck(
                "baseline",
                "warning",
                f"Automatic diff baseline is unavailable: {exc}",
            ))
        else:
            checks.append(DoctorCheck(
                "baseline",
                "pass",
                f"Automatic diff baseline resolves to {base_ref}.",
            ))

    checks.append(_check_workflow(root))
    return DoctorReport(str(root), tuple(checks))
