# Deletion approval: configuration review and execution

This prototype pairs two separately enforced checks:

1. Installed **ACS v0.26.1** reviews a Cursor rule change. Narrowing the glob
   stops the declared deletion-approval instruction from covering the selected
   target. Both standalone scores remain 100; the opt-in review exits 1.
2. The independent example host executor in [gate.py](gate.py) refuses a
   `delete_file` request until it has matching operator approval. It checks the
   actual filesystem after each scripted request.

The runnable example uses local temporary files, no model API, no network and
no new runtime dependencies. See the [challenge walkthrough](../../docs/ai-safety-challenge.md)
and [recorded replay](recorded/result.md).

The [assistant-operated smoke](assistant-recorded/README.md) separately records
four requests from the maintainer's Codex session. It uses host-simulated
approval and does not validate agent isolation. The [one-minute walkthrough](../../assets/agent-config-score-approval.mp4)
renders these two evidence categories separately from their retained JSON.

## Try the operator console

From a checkout of this repository, using Python 3.10+:

```bash
python examples/approval-gate/try_gate.py
```

The first request is refused. The console then shows the disposable file and
asks the operator to type `DELETE`. Refusal leaves the file present until normal
temporary-workspace cleanup. Approval actually deletes that one file. Existing
user paths cannot be supplied to this console. The operator console must remain
outside the agent's tool access.

## Reproduce both layers

Install ACS in your selected Python environment, then run from the checkout:

```bash
python -m pip install agent-config-score==0.26.1
python scripts/run_approval_demo.py --output-dir approval-demo-result
```

`approval-demo-result` must not exist. Use `--python /absolute/path/to/python`
when ACS is installed in another environment. The subprocess uses isolated
Python from a temporary working directory, so repository sources cannot silently
replace the installed ACS. It is offline after installation. The example and
runner are repository files, separate from the installed wheel.

Completion writes `result.json` with installed source identity, normalized-text
SHA-256 input hashes, full static comparisons and execution decisions, plus
`result.md` for reading. Exit 0 means the registered synthetic scenarios and
their filesystem postconditions matched; exit 2 means replay or output failed.
Do not treat a partial output directory after failure as completed evidence.

The 12 scripted execution scenarios cover missing approval, self-approval,
invented tokens, expiry, target mismatch, changed content, file replacement,
different sessions, traversal, unregistered tools, authorized deletion and replay.
Approvals in this replay come from the **trusted test harness**, not a human or
a live agent. Two files are actually deleted: the authorized case and the replay
setup. Every scenario checks that unrelated sentinels are preserved.

```bash
python -m unittest discover -s tests -p test_approval_gate_demo.py -v
```

Additional tests cover root/parent replacement, hard links, symbolic links when
permitted, invalid lifetimes, size limits and filesystem failure. A filesystem
error returns `error` with `executed: null` (outcome requires inspection), not a
successful refusal. Once execution is attempted, that grant is consumed even on
an I/O error; another attempt requires fresh approval.

## Approval contract

The trusted host obtains separate operator and tool handles:

```python
operator, delete_file = create_session(disposable_workspace)
# Operator reviews the proposed relative path and file content outside agent access.
token = operator.approve("obsolete.txt", ttl_seconds=30)
result = delete_file({"tool": "delete_file", "path": "obsolete.txt", "approval": token})
```

Only `delete_file` belongs in the agent registry. `Operator.approve` is the
trusted issuance API; it does not itself authenticate a human. The host must
perform that authentication/review before calling it. `approved: true` is
rejected. An opaque token is bound to the session, exact portable relative path,
parent identities, file identity, size, modification time, content digest,
host-clock expiry (maximum 60 seconds) and one attempt. POSIX ctime is also
checked; Python 3.12 exposes differing legacy ctime semantics on Windows, so
Windows uses the other recorded signals. No raw token is written to reports.

## Trust boundary and limitations

- **Exclusively owned, stable local workspace.** No other process may mutate
  files or ancestors during approval/execution. Python checks followed by unlink
  are not an atomic defense against hostile concurrent filesystem changes.
  The lock serializes this example's own operations only.
- **Tool-only agent access.** The agent cannot execute arbitrary Python, run a
  shell, access host filesystem APIs, inspect operator state or call another
  deletion channel. In-process Python handles are not a security isolation
  boundary. A real deployment must enforce this separation outside agent control.
- **One regular file.** The gate refuses directories, recursive deletion,
  symlinks/reparse points, hard links, nonportable paths and files above 1 MiB.
  It is intentionally unsuitable as a general file-management API.
- **Process-local grants.** Restart forgets approvals. Persistent identity,
  distributed execution, signed audit storage, approval UI security, OS sandboxing
  and adversarial races are not implemented.
- **Separate layers.** Static ACS predicts declared instruction availability;
  it does not inspect these calls or prove the agent followed the instruction.
  This example enforces approval only for its registered operation. Rule text
  is never evaluated as executable policy. The wrapper is not a shipped ACS
  runtime capability.

These are development controls, not independent accuracy evidence or a claim
that arbitrary irreversible actions are prevented. Production adoption needs
review of the host, its tools, approver authentication and execution boundary.
