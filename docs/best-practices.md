# Practical instruction-file review checklist

This is **advisory documentation**, not a scored checklist or a promise that an
agent obeys Markdown. Use the parts relevant to the agent and repository in use.
Do not copy keywords into a file to improve its score.

## Keep instructions actionable and current

- Describe the actual repository and the setup, build, test or lint commands a
  contributor needs. Do not invent commands from a generic template.
- Reference existing files for detailed architecture and task-specific guidance.
  When a directory or document moves, update its references in instruction files.
- Distinguish required verification from optional checks. Reports should say
  what passed, failed or was not run; a skipped check is not a passing check.
- Keep examples clearly labeled and separate from active policy. A dangerous
  command shown as a prohibited example has a different meaning from an action
  an agent is told to execute.

## Keep scope explicit

- Check which instruction filenames, nesting rules and tool-specific settings
  the actual agent supports. A file existing does not prove that it is loaded.
- Put shared guidance in a maintained location only when the tools in use can
  load it. Do not assume every agent combines files or resolves conflicts alike.
- Keep genuinely package-specific instructions near their scope. Review scope
  changes when moving/removing files, even if their text stays identical.
- Review contradictory instructions rather than retaining both and expecting
  the agent to infer the intended policy.

## Treat safety as a workflow, not a sentence

- Keep credentials and private key material out of instruction files. If real
  credentials are exposed, removing the line alone does not resolve exposure.
- State the repository's actual approval and boundary rules for deleting files,
  overwriting user changes and other destructive operations. Avoid generic bans
  that contradict legitimate workflows or stricter existing rules.
- Use runtime permissions and isolation appropriate to the tool. Written
  approval requirements are not an enforcement mechanism by themselves.
- Treat external content, examples and tool output as data unless explicitly
  authorized as instructions. Review attempts to override existing constraints.
  A small phrase detector is not a comprehensive prompt-injection defense.

## Apply and verify changes

Use the [maintainer workflow](maintainer-workflow.md) to inspect concrete
findings and suggested next steps. The tool never runs referenced commands to
validate them, and path existence does not establish that the target is correct.
Review any edits and rerun the relevant checks after making them.

The optional [deletion-safeguard preview](guardrail-suggestions.md) can propose
text for one selected file. Review the full policy context before applying it;
missing recognized wording does not prove that the repository lacks protection.

A clean scan means no supported active rule matched, **not** that every item
above was verified. See the [limits](limitations.md), [instruction context](instruction-context.md)
and [regression coverage](regression-coverage.md). For the public instruction-file
format, see the [AGENTS.md project](https://github.com/agentsmd/agents.md).
