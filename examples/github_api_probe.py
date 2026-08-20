#!/usr/bin/env python3
"""Prototype GitHub API integration for AgentConfigScore.

This small development integration probes a public GitHub repository for common
AI coding-agent configuration files. It uses only Python's standard library and
optionally accepts a GITHUB_TOKEN for authenticated API requests.

Usage:
    python examples/github_api_probe.py owner/repository
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CONFIG_PATHS = (
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
    ".clinerules",
    ".windsurfrules",
)


def github_get(url: str) -> tuple[int, object | None]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AgentConfigScore-GitHub-API-Prototype",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return 404, None
        raise


def probe(repository: str) -> dict[str, object]:
    if repository.count("/") != 1:
        raise ValueError("repository must be in owner/name form")

    owner, name = repository.split("/", 1)
    base = f"https://api.github.com/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}"

    status, metadata = github_get(base)
    if status != 200 or not isinstance(metadata, dict):
        raise RuntimeError(f"repository not found: {repository}")

    found: list[str] = []
    for path in CONFIG_PATHS:
        encoded_path = "/".join(urllib.parse.quote(part) for part in path.split("/"))
        path_status, _ = github_get(f"{base}/contents/{encoded_path}")
        if path_status == 200:
            found.append(path)

    return {
        "repository": repository,
        "default_branch": metadata.get("default_branch"),
        "visibility": metadata.get("visibility"),
        "agent_config_files": found,
        "count": len(found),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python examples/github_api_probe.py owner/repository", file=sys.stderr)
        return 2

    try:
        result = probe(sys.argv[1])
    except (ValueError, RuntimeError, urllib.error.URLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
