from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

CONFIG_NAME = ".agentconfigscore.json"


class ConfigError(ValueError):
    """Raised when AgentConfigScore repository configuration is invalid."""


@dataclass(frozen=True)
class Policy:
    max_drop: int = 0
    fail_on_new_errors: bool = False
    fail_under: int | None = None


_ALLOWED_TOP_LEVEL = {"version", "policy"}
_ALLOWED_POLICY_KEYS = {"max_drop", "fail_on_new_errors", "fail_under"}


def _require_int(name: str, value, *, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        if maximum is None:
            raise ConfigError(f"{name} must be >= {minimum}")
        raise ConfigError(f"{name} must be between {minimum} and {maximum}")
    return value


def parse_policy(data: object) -> Policy:
    if not isinstance(data, dict):
        raise ConfigError("configuration root must be a JSON object")

    unknown = sorted(set(data) - _ALLOWED_TOP_LEVEL)
    if unknown:
        raise ConfigError(f"unknown configuration key(s): {', '.join(unknown)}")

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

    return Policy(
        max_drop=max_drop,
        fail_on_new_errors=fail_on_new_errors,
        fail_under=fail_under,
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
