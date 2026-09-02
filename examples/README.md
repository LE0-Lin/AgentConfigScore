# Copy-ready instruction examples

These templates provide conservative repository workflow, verification, safety,
and handoff guidance without assuming a programming language or package manager.
Copy one into the matching path in your repository, then adapt it to your real
commands and architecture.

| Tool | Copy this file to your repository | Format reference |
|---|---|---|
| Cursor | `cursor/.cursor/rules/project.mdc` → `.cursor/rules/project.mdc` | [Cursor Project Rules](https://docs.cursor.com/context/rules) |
| GitHub Copilot | `copilot/.github/copilot-instructions.md` → `.github/copilot-instructions.md` | [GitHub custom instructions](https://docs.github.com/en/copilot/reference/custom-instructions-support) |
| Gemini CLI | `gemini/GEMINI.md` → `GEMINI.md` | [Gemini CLI context files](https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md#context-files-hierarchical-instructional-context) |
| Claude Code | `claude-code/CLAUDE.md` → `CLAUDE.md` | [Claude Code memory](https://docs.anthropic.com/en/docs/claude-code/memory) |

The small `cursor/.cursorrules` fixture remains for legacy compatibility tests;
Cursor documents that format as deprecated, so new projects should copy the MDC
Project Rule above.

For example, from this repository on macOS or Linux:

```bash
mkdir -p ../your-project/.cursor/rules
cp examples/cursor/.cursor/rules/project.mdc ../your-project/.cursor/rules/project.mdc
agent-config-score ../your-project
```

PowerShell equivalent:

```powershell
New-Item -ItemType Directory -Force ..\your-project\.cursor\rules
Copy-Item examples\cursor\.cursor\rules\project.mdc ..\your-project\.cursor\rules\project.mdc
agent-config-score ..\your-project
```

Scan templates individually when evaluating them in this repository; scanning
the whole `examples/` tree intentionally compares several alternative tools at
once and may report cross-file duplication.
