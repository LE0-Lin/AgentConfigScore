"""Small, tool-only deletion gate for an exclusively owned local demo workspace.

This is example host code, not an ACS runtime feature or an OS sandbox. An agent
must have access only to the returned tool callable, never the operator handle,
host interpreter, filesystem APIs or another deletion tool. The host must prevent
concurrent filesystem mutation. See README.md for the complete trust boundary.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import re
import secrets
import stat
import threading
import time


MAX_FILE_BYTES = 1024 * 1024


class Refused(ValueError):
    pass


def _is_alias(info) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _identity(info) -> tuple:
    return info.st_dev, info.st_ino


class _State:
    def __init__(self, root: Path, clock):
        if _is_alias(root.lstat()) or not root.is_dir():
            raise Refused("workspace_not_regular_directory")
        self.root = root.resolve()
        self.root_identity = _identity(self.root.lstat())
        self.clock = clock
        self.grants = {}
        self.lock = threading.Lock()

    def target(self, value) -> Path:
        if (type(value) is not str or not value or len(value) > 512
                or not re.fullmatch(r"[A-Za-z0-9_./-]+", value)):
            raise Refused("invalid_relative_path")
        parts = value.split("/")
        if any(not p or p in {".", ".."} or p.endswith(".") or len(p) > 128
               or p.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)],
                                              *[f"LPT{i}" for i in range(1, 10)]} for p in parts):
            raise Refused("invalid_relative_path")
        root_info = self.root.lstat()
        if _is_alias(root_info) or _identity(root_info) != self.root_identity or not stat.S_ISDIR(root_info.st_mode):
            raise Refused("workspace_changed")
        target = self.root.joinpath(*parts)
        if not target.is_relative_to(self.root):
            raise Refused("outside_workspace")
        return target

    def snapshot(self, path: str) -> tuple:
        target = self.target(path)
        parents = []
        current = self.root
        for part in path.split("/")[:-1]:
            current = current / part
            info = current.lstat()
            if _is_alias(info) or not stat.S_ISDIR(info.st_mode):
                raise Refused("aliased_or_invalid_parent")
            parents.append(_identity(info))
        before = target.lstat()
        if _is_alias(before) or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise Refused("target_not_single_regular_file")
        if before.st_size > MAX_FILE_BYTES:
            raise Refused("target_size_limit")
        descriptor = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
        with os.fdopen(descriptor, "rb") as source:
            opened = os.fstat(source.fileno())
            if (_identity(opened) != _identity(before) or not stat.S_ISREG(opened.st_mode)
                    or opened.st_nlink != 1):
                raise Refused("target_changed")
            raw = source.read(MAX_FILE_BYTES + 1)
            after = os.fstat(source.fileno())
        # Windows 3.12 path stat and fd stat expose different legacy ctime
        # semantics. Identity + mtime + size + content still bind the grant;
        # retain ctime as an additional mutation signal on POSIX only.
        stamp = lambda s: (_identity(s), s.st_size, s.st_mtime_ns,
                           s.st_ctime_ns if os.name != "nt" else None)
        if len(raw) > MAX_FILE_BYTES or stamp(before) != stamp(after) or stamp(target.lstat()) != stamp(after):
            raise Refused("target_changed")
        return tuple(parents), stamp(after), hashlib.sha256(raw).hexdigest()


class Operator:
    """Trusted host/operator handle. Never place this in the agent tool registry."""

    def __init__(self, state):
        self._state = state

    def approve(self, path: str, *, ttl_seconds=30) -> str:
        if (type(ttl_seconds) not in (int, float) or not math.isfinite(ttl_seconds)
                or not 0 < ttl_seconds <= 60):
            raise Refused("invalid_approval_lifetime")
        with self._state.lock:
            snapshot = self._state.snapshot(path)
            token = secrets.token_urlsafe(32)
            self._state.grants[token] = {"path": path, "snapshot": snapshot,
                                         "expires": self._state.clock() + ttl_seconds, "used": False}
            return token


class DeleteTool:
    """The only registered agent operation in this demonstration."""

    def __init__(self, state):
        self._state = state

    def __call__(self, request) -> dict:
        def denied(reason):
            return {"decision": "denied", "reason": reason, "executed": False}

        if type(request) is not dict or set(request) - {"tool", "path", "approval"}:
            return denied("invalid_request_schema")
        if request.get("tool") != "delete_file":
            return denied("unregistered_tool")
        try:
            with self._state.lock:
                target = self._state.target(request.get("path"))
                token = request.get("approval")
                if token is None:
                    return denied("approval_required")
                if type(token) is not str or len(token) > 128:
                    return denied("invalid_approval")
                grant = self._state.grants.get(token)
                if grant is None:
                    return denied("invalid_approval")
                if grant["used"]:
                    return denied("approval_already_used")
                if self._state.clock() >= grant["expires"]:
                    return denied("approval_expired")
                if request["path"] != grant["path"]:
                    return denied("approval_target_mismatch")
                if self._state.snapshot(request["path"]) != grant["snapshot"]:
                    return denied("approved_state_changed")
                # Consume before the effect; I/O failure also needs fresh approval.
                grant["used"] = True
                target.unlink()
                return {"decision": "executed", "reason": "matching_operator_approval", "executed": True}
        except Refused as error:
            return denied(str(error))
        except OSError:
            # No raw paths, OS messages or approval tokens in shareable results.
            # An OS error is not proof that no effect occurred; require inspection.
            return {"decision": "error", "reason": "filesystem_error", "executed": None}


def create_session(root: Path, *, clock=time.monotonic) -> tuple[Operator, DeleteTool]:
    """Register the approved root once. Approval state is local to this session."""
    state = _State(root, clock)
    return Operator(state), DeleteTool(state)
