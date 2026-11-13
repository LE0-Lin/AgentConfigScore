# Native Cursor behavioral smoke check

Completed **2026-11-13**, with a user operating **Cursor desktop 3.29.15 on
Windows x64**. The model picker showed **Grok 4.7** at setup; the backend model
snapshot was not attested per run. Predictions came from the unchanged published
**ACS v0.26.1** wheel, with its retained runtime source identity.

Four automatic file-context cases produced visible marker sets matching the
frozen predictions. One explicit-selection control also emitted its requested
marker. **This is a small native behavioral smoke check, not a complete attachment
trace, general compatibility guarantee or independent accuracy study.**

## Observations

| Case / screenshot | Explicit file context | Predicted active rule names | Visible marker names | Observed file reads |
| --- | --- | --- | --- | --- |
| [API only](screenshots/api-only.png) | `src/api/service.py` | ALWAYS, API | ALWAYS, API | `src/api/service.py` |
| [Web only](screenshots/web-only.png) | `src/web/app.ts` | ALWAYS, WEB | ALWAYS, WEB | `src/web/app.ts` |
| [Joint](screenshots/joint.png) | Both files above | ALWAYS, API, WEB | ALWAYS, API, WEB | Both files above |
| [Root TypeScript](screenshots/root-ts.png) | `index.ts` | ALWAYS, ROOT_ONLY | ALWAYS, ROOT_ONLY | `index.ts` |
| [Explicit-selection control](screenshots/manual-control.png) | Select `always.mdc` | Control expects ALWAYS | ALWAYS | No read event retained |

Five distinct conversation identifiers and ten native events were retained:
five prompt events and five file-read events. The fixture's rule, target and
collector bytes stayed unchanged. Observed reads were all declared targets;
these two hooks are not assumed to record every possible action.

The last control selects an **always-apply** rule. It checks that the marker
response can be elicited with deliberate selection; it does not independently
validate a manual-only rule mode.

[Prepared inputs](prepared-inputs.json) retain random marker keys, original
hashes and complete frozen ACS predictions. Keys and predictions were outside
the workspace, not in prompts or target code. [Observations](observations.json)
contain assistant transcriptions of user-supplied screenshots. These are not
OCR, independent labels or complete exported transcripts. Cropped screenshots
are retained for inspection; account UI screenshots are not published.

## Preserved observability limits

The [original protocol](protocol.json) used neutral rules and proposed reading
native hook attachment lists. Actual lists remained empty even with a visible
explicit rule chip. The diagnostic collector recorded the raw count before
filtering: zero attachments, zero discarded entries. [Initial events](initial-hook-events.jsonl)
preserve both collector versions. The [transcript export](initial-transcript.md)
contained conversation text and a rule name, not its body or full context.
No Context Usage entry was visible in the supplied full-window screenshot;
the component's presence in installed code did not establish UI availability.

These limits were preserved. A [behavior addendum](behavior-protocol.json)
declared the separate marker experiment before queries. Preparation was committed
at `c97f307` before the five observed queries. This is local evidence ordering,
not independently timestamped preregistration. The user selected target file
chips in fresh chats and supplied screenshots; no assistant model run was
substituted for the native client.

Marker appearance is behavior consistent with access to a rule body. Missing
markers could be noncompliance. Neither outcome identifies the complete hidden
prompt or proves how a rule became available. User/team settings were not
independently captured. There was one run per context, with no alternate-model,
OS, nested-workspace, adversarial or long-session measurement. Do not turn these
counts into general accuracy or security claims.

## Verify retained evidence offline

From a checkout with Python 3.10+:

```bash
python scripts/verify_cursor_native_evidence.py
```

This checks the integrity index, fixture hashes, distinct conversations, event
attribution and transcribed marker sets against frozen predictions. Disagreements
remain completed observations. Exit zero means offline verification completed;
it does not mean Cursor was rerun or is safe. The index is not authentication.

For a **new** user-operated native run with an installed v0.26.1 wheel:

```bash
python scripts/prepare_cursor_behavior_probe.py --workspace /path/to/new-probe --evidence-dir /path/to/separate-evidence --python /path/to/frozen-env/bin/python
```

On Windows, use the environment's `Scripts/python.exe`. The generator launches
the installed package with isolated Python flags and checks its source identity.
It creates fresh random markers, neutral code and project hooks. It never calls
a model or uploads files. Keep keys outside the workspace; run each generated
prompt in a fresh chat, explicitly select its files, and retain all outcomes.

[Fixture](fixture) retains all captured input bytes except the host-specific
hook command configuration. Its original hash is retained, but absolute local
interpreter/workspace paths are omitted. Generate commands for your own machine.
Keep collector unit-test events separate from real native observations.
