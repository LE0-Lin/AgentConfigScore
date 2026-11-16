# Can ACS catch problems in its own instructions?

We tested the published **v0.26.2** wheel against copies of our own complete
tracked repository at `b782906aeea0dbfc3e99d1d7e95a81a699741c97`.
The untouched baseline scores **100**, with no active findings in five supported
instruction files: root `AGENTS.md` and the Claude, Cursor, Copilot and Gemini
examples. Ordinary README files are not treated as agent instructions.

The [retained raw report](evidence/self-use-0262.json) includes the source revision,
archive hash, installed tool identity, original case text, scan findings,
comparison findings and actual process exits. All modifications took place in
disposable copies; no deletion, network installer or other instruction was run.

## Working behavior and limits

| Change to our actual root instructions | Scan score | Scan exit | Compare exit |
|---|---:|---:|---:|
| No change | 100 | 0 | 0 |
| Recommend `rm -rf build` | 89 | 1 | 1 |
| Prohibit that same deletion command | 100 | 0 | 0 |
| Link to a nonexistent guide | 96 | 0 | 1 |
| Correct the link to the existing user guide | 100 | 0 | 0 |
| Require claiming that failed tests passed | 88 | 1 | 1 |
| Recommend piping a remote installer into bash | 82 | 1 | 1 |
| Recommend deletion and weaken the candidate policy | 89 | 0 | 1 |
| Empty the root instruction file | 70 | 1 | 1 |

The standalone scan applies its candidate's score floor, which our fixture sets
to 90. A missing guide is only a four-point warning, so the standalone command
returns success at 96. **Use baseline comparison for a PR gate**: the baseline's
zero-drop and new-error policies reject that regression. A PR lowering its own
threshold to zero also cannot authorize the deletion regression against the
unchanged baseline. Exit 0 never means every instruction is safe.

We also ran three explicit limitation probes. These are **observations, not
passing detection tests**:

| Instruction change | Observed score | Observed gate |
|---|---:|---|
| Replace useful root guidance with “Do a good job.” | 100 | Pass |
| Authorize removing the production database without confirmation, using prose rather than a recognized command | 100 | Pass |
| Require falsely claiming tests passed, written in Chinese | 100 | Pass |

These results directly rule out using ACS as a complete instruction safety or
semantic quality reviewer. A 100 means no active deterministic rule matched;
it cannot distinguish all useful instructions from vague or unsafe ones.
Localized documentation/output does not imply semantic detection in those
languages. A maintainer should review important policy changes and use other
checks for behavior outside the documented rule grammar.

The separate, **unscored** `guardrails` review also notices that the original
root `AGENTS.md` does not state deletion/overwrite approval safeguards, despite
its 100 score. We used that finding to add explicit approval guidance to our own
root file in this maintenance change. This improves our instructions; it is not
runtime enforcement, and it does not solve the semantic probes above.

## Reproduce locally

Create an isolated environment, install ACS 0.26.2, then run from a local ACS
checkout containing the pinned source revision:

```bash
python scripts/run_self_acceptance.py --python /path/to/venv/bin/python \
  --ref b782906aeea0dbfc3e99d1d7e95a81a699741c97 --output self-use-new.json
```

On Windows, pass the environment's `Scripts/python.exe`. The controller uses
only the standard library and local Git; the worker uses the specified installed
ACS package in isolated mode. Package installation needs network access; the
replay itself does not. Existing output files are never overwritten. `--ref HEAD`
tests the current committed repository; it does not test uncommitted changes.

The nine known acceptance contracts must match their declared rule IDs and gate
exits. The three limitation probes remain descriptive: detecting one after a
future improvement must not fail the runner. A failed contract is retained in
the JSON result and returns exit 1. Operational failures do not produce a clean
report. Installed-wheel CI replays these checks on Linux, Windows and macOS.

This is **maintainer-authored development acceptance**, not independent accuracy
or evidence that another maintainer uses ACS. It supports a small read-only trial
of the bounded linter; it does not justify promising a comprehensive security
audit. See [rule and score limitations](limitations.md) and the
[maintainer workflow](maintainer-workflow.md) before selecting a gate policy.
