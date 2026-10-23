"""Best-effort identity of the tool's own source, never repository inputs."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import resources
import json

from . import __version__


SOURCE_FORMAT = "acs-python-source-v1"
# Explicit coverage: no recursive reads, repository files, Git commands or imports.
# Keep sorted and include new runtime modules when they are added.
SOURCE_FILES = (
    "__init__.py", "__main__.py", "cli.py", "config.py", "doctor.py",
    "entrypoint.py", "feedback.py", "gitdiff.py", "guardrails.py", "history.py", "initializer.py",
    "provenance.py", "regression.py", "rules.py", "sarif.py", "scanner.py",
)


@dataclass(frozen=True)
class ToolIdentity:
    version: str
    source_sha256: str | None
    source_format: str = SOURCE_FORMAT
    source_files: tuple[str, ...] = SOURCE_FILES

    def to_dict(self) -> dict:
        return {
            "name": "AgentConfigScore",
            "version": self.version,
            "source_fingerprint": {
                "format": self.source_format,
                "sha256": self.source_sha256,
                "files": list(self.source_files),
            },
        }


def capture_tool_identity() -> ToolIdentity:
    """Capture installed source bytes, not an attestation of executing bytecode.

    Do not cache: long-lived callers may change their installation between scans.
    Missing/unreadable source makes the entire digest unknown, not a partial hash.
    """
    try:
        package = resources.files(__package__)
        sources = []
        for name in SOURCE_FILES:
            text = package.joinpath(name).read_text(encoding="utf-8")
            sources.append([name, text.replace("\r\n", "\n").replace("\r", "\n")])
        payload = json.dumps(sources, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    except (OSError, UnicodeError):
        # Do not expose installation paths or raw I/O errors in shareable reports.
        digest = None
    return ToolIdentity(__version__, digest, SOURCE_FORMAT, SOURCE_FILES)
