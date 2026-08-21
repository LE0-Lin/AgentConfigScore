from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from fnmatch import fnmatch
import json
from pathlib import Path

from .rules import get_rule

CONFIG_NAME = ".agentconfigscore.json"
SCHEMA_URL = "https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/v0/schema/agentconfigscore.schema.json"


class ConfigError(ValueError):
    """Raised when AgentConfigScore repository configuration is invalid."""


@dataclass(frozen=True)
class Suppression:
    rule: str
    reason: str
    expires: date
    paths: tuple[str, ...] = ()

    def applies_to(self, rule: str, file: str) -> bool:
        if self.rule != rule:
            return False
        if not self.paths:
            return True
        if file == "(repo)":
            return False
        return any(fnmatch(file, pattern) for pattern in self.paths)

    def to_dict(self) -> dict:
        data = {
            "rule": self.rule,
            "reason": self.reason,
            "expires": self.expires.isoformat(),
        }
        if self.paths:
            data["paths"] = list(self.paths)
        return data


@dataclass(frozen=True)
class Policy:
    max_drop: int = 0
    fail_on_new_errors: bool = False
    fail_under: int | None = None
    suppressions: tuple[Suppression, ...] = ()


_ALLOWED_TOP_LEVEL = {"$schema", "version", "policy", "suppressions"}
_ALLOWED_POLICY_KEYS = {"max_drop", "fail_on_new_errors", "fail_under"}
_ALLOWED_SUPPRESSION_KEYS = {"rule", "reason", "expires", "paths"}


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _require_int(name: str, value, *, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        if maximum is None:
            raise ConfigError(f"{name} must be >= {minimum}")
        raise ConfigError(f"{name} must be between {minimum} and {maximum}")
    return value


def _parse_suppression(raw: object, index: int, *, today: date) -> Suppression:
    name = f"suppressions[{index}]"
    if not isinstance(raw, dict):
        raise ConfigError(f"{name} must be a JSON object")

    unknown = sorted(set(raw) - _ALLOWED_SUPPRESSION_KEYS)
    if unknown:
        raise ConfigError(f"unknown {name} key(s): {', '.join(unknown)}")

    rule = raw.get("rule")
    if not isinstance(rule, str) or not rule.strip():
        raise ConfigError(f"{name}.rule must be a non-empty string")
    rule = rule.strip()
    if get_rule(rule) is None:
        raise ConfigError(f"{name}.rule references unknown rule ID: {rule}")

    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ConfigError(f"{name}.reason must be a non-empty string")
    reason = reason.strip()
    if len(reason) > 500:
        raise ConfigError(f"{name}.reason must be at most 500 characters")

    expires_raw = raw.get("expires")
    if not isinstance(expires_raw, str):
        raise ConfigError(f"{name}.expires must be an ISO date (YYYY-MM-DD)")
    try:
        expires = date.fromisoformat(expires_raw)
    except ValueError as exc:
        raise ConfigError(f"{name}.expires must be an ISO date (YYYY-MM-DD)") from exc
    if expires.isoformat() != expires_raw:
        raise ConfigError(f"{name}.expires must use YYYY-MM-DD format")
    if expires < today:
        raise ConfigError(
            f"{name} expired on {expires.isoformat()}; remove it or renew it with a reviewed reason"
        )

    raw_paths = raw.get("paths")
    paths: tuple[str, ...] = ()
    if raw_paths is not None:
        if not isinstance(raw_paths, list) or not raw_paths:
            raise ConfigError(f"{name}.paths must be a non-empty JSON array when provided")
        normalized: list[str] = []
        for path_index, value in enumerate(raw_paths):
            if not isinstance(value, str) or not value.strip():
                raise ConfigError(f"{name}.paths[{path_index}] must be a non-empty string")
            normalized.append(value.strip())
        if len(set(normalized)) != len(normalized):
            raise ConfigError(f"{name}.paths must not contain duplicates")
        paths = tuple(normalized)

    return Suppression(rule=rule, reason=reason, expires=expires, paths=paths)


def parse_policy(data: object, *, today: date | None = None) -> Policy:
    if not isinstance(data, dict):
        raise ConfigError("configuration root must be a JSON object")

    unknown = sorted(set(data) - _ALLOWED_TOP_LEVEL)
    if unknown:
        raise ConfigError(f"unknown configuration key(s): {', '.join(unknown)}")

    schema_uri = data.get("$schema")
    if schema_uri is not None and (not isinstance(schema_uri, str) or not schema_uri.strip()):
        raise ConfigError("$schema must be a non-empty string when provided")

    version = data.get("version", 1)
    if version != 1:
        raise ConfigError("version must be 1")

    raw_policy = data.get("policy", {})
    if not isinstance(raw_policy, dict):
        raise ConfigError("policy must be a JSON object")

    unknown_policy = sorted(set(raw_policy) - _ALLOWED_POLICY_KEYS)
    if unknown_policy:
        raise ConfigError(f"unknown policy key(s): {', '.join(unknown_policy)}")

    max_drop = _require_int("policy.max_drop", raw_policy.get("max_drop", 0), minimum=0)

    fail_on_new_errors = raw_policy.get("fail_on_new_errors", False)
    if not isinstance(fail_on_new_errors, bool):
        raise ConfigError("policy.fail_on_new_errors must be true or false")

    fail_under = raw_policy.get("fail_under")
    if fail_under is not None:
        fail_under = _require_int("policy.fail_under", fail_under, minimum=0, maximum=100)

    raw_suppressions = data.get("suppressions", [])
    if not isinstance(raw_suppressions, list):
        raise ConfigError("suppressions must be a JSON array")
    evaluation_date = _utc_today() if today is None else today
    suppressions = tuple(
        _parse_suppression(raw, index, today=evaluation_date)
        for index, raw in enumerate(raw_suppressions)
    )

    identities = [(item.rule, item.paths) for item in suppressions]
    if len(set(identities)) != len(identities):
        raise ConfigError("duplicate suppressions for the same rule and path scope are not allowed")

    return Policy(
        max_drop=max_drop,
        fail_on_new_errors=fail_on_new_errors,
        fail_under=fail_under,
        suppressions=suppressions,
    )


def load_policy(root: Path) -> Policy:
    path = root.resolve() / CONFIG_NAME
    if not path.exists():
        return Policy()
    if not path.is_file():
        raise ConfigError(f"{CONFIG_NAME} exists but is not a file")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"could not read {CONFIG_NAME}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"invalid JSON in {CONFIG_NAME} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    try:
        return parse_policy(data)
    except ConfigError as exc:
        raise ConfigError(f"invalid {CONFIG_NAME}: {exc}") from exc
