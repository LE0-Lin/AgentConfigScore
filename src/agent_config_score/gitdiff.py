from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import subprocess
import tempfile

from .regression import RegressionReport, compare


class GitError(RuntimeError):
    """Raised when a Git-backed comparison cannot be prepared safely."""


_DEFAULT_BRANCH_NAMES = ("main", "master", "trunk")


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise GitError("git executable not found on PATH") from exc


def repository_root(path: Path) -> Path:
    path = path.resolve()
    if not path.exists() or not path.is_dir():
        raise GitError(f"not a directory: {path}")

    proc = _run_git(path, "rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        raise GitError(f"not a Git repository: {path}")
    return Path(proc.stdout.strip()).resolve()


def _ref_exists(repo: Path, ref: str) -> bool:
    proc = _run_git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
    return proc.returncode == 0


def detect_base_ref(repo: Path) -> str:
    """Detect a conservative local baseline without fetching from the network."""
    repo = repository_root(repo)

    # A locally configured origin/HEAD is the closest Git-native signal for
    # the repository's default branch and does not require network access.
    origin_head = _run_git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if origin_head.returncode == 0:
        ref = origin_head.stdout.strip()
        if ref and _ref_exists(repo, ref):
            return ref

    # Prefer conventional local default-branch names over a feature branch's
    # upstream. Comparing a feature branch with origin/feature would hide the
    # very committed changes a regression gate is supposed to evaluate.
    for name in _DEFAULT_BRANCH_NAMES:
        if _ref_exists(repo, name):
            return name

    upstream = _run_git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if upstream.returncode == 0:
        ref = upstream.stdout.strip()
        leaf = ref.rsplit("/", 1)[-1]
        if leaf in _DEFAULT_BRANCH_NAMES and _ref_exists(repo, ref):
            return ref

    raise GitError(
        "cannot detect a baseline Git ref. Pass one explicitly (for example: "
        "agent-config-score diff origin/main), or configure origin/HEAD / a local main, master, or trunk branch."
    )


def resolve_commit(repo: Path, ref: str) -> str:
    proc = _run_git(repo, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}")
    if proc.returncode != 0:
        raise GitError(
            f"cannot resolve Git ref '{ref}'. Fetch it first (for example: git fetch origin) "
            "or pass a local branch, tag, or commit."
        )
    return proc.stdout.strip()


@contextmanager
def baseline_worktree(repo: Path, ref: str):
    sha = resolve_commit(repo, ref)
    with tempfile.TemporaryDirectory(prefix="agent-config-score-") as temp_dir:
        worktree = Path(temp_dir) / "base"
        proc = _run_git(repo, "worktree", "add", "--detach", "--quiet", str(worktree), sha)
        if proc.returncode != 0:
            detail = proc.stderr.strip() or proc.stdout.strip() or "unknown Git worktree error"
            raise GitError(f"could not create baseline worktree for '{ref}': {detail}")
        try:
            yield worktree, sha
        finally:
            _run_git(repo, "worktree", "remove", "--force", str(worktree))
            _run_git(repo, "worktree", "prune")


def compare_git_ref(path: Path, ref: str) -> RegressionReport:
    repo = repository_root(path)
    with baseline_worktree(repo, ref) as (base, sha):
        report = compare(base, repo)
    report.base.root = f"git:{ref}@{sha[:12]}"
    report.head.root = str(repo)
    return report
