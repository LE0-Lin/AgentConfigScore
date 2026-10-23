# Report tool identity

Available in **v0.24.0+**. Earlier reports and frozen research artifacts are not
retroactively relabelled with the new version or source fingerprint.

Package versions alone do not distinguish unreleased checkouts or local patches.
New scans capture a `tool` object at the start of `analyze()`, with:

- `name`: `AgentConfigScore`.
- `version`: the package's declared version, not a claim that this is an official release.
- `source_fingerprint.format`: `acs-python-source-v1`.
- `source_fingerprint.sha256`: 64 lowercase hex characters, or `null` if any
  covered source is missing, unreadable or not valid UTF-8. No partial digest is used.
- `source_fingerprint.files`: the ordered, explicit package-source coverage list.

The fingerprint reads **only the tool's own listed Python source files**. It does
not read the scanned project's contents for hashing, run Git, contact a service,
execute those source files or add a runtime dependency. A private project name,
path, instruction, credential, configuration or suppression is not a fingerprint
input. Locally patched tool source does affect the digest; review feedback before
sharing it as usual.

## Fingerprint format

For `acs-python-source-v1`, read every filename in the exported list from the
`agent_config_score` package as strict UTF-8. Normalize CRLF and lone CR to LF.
Construct a list of `[filename, normalized_text]` pairs in the exported order.
Serialize with Python `json.dumps(pairs, ensure_ascii=False, separators=(",", ":"))`,
encode as UTF-8, and SHA-256 those bytes. Whitespace and comments otherwise remain
significant. LF and CRLF checkouts with identical text therefore have the same
digest. A test requires the manifest to cover every top-level runtime `.py` module;
new source formats or normalization rules require a new format identifier.

## Where it appears

Scan JSON exposes `tool`; compare/diff JSON exposes it on both `base` and `head`.
SARIF preserves it at `runs[].tool.driver.properties.toolIdentity` and uses the
captured package version for `semanticVersion`. HTML displays the captured version
and source SHA-256, separately from its existing short **report** fingerprint.
New history snapshots retain `tool`. Privacy-minimized feedback includes the
captured version and tool-source digest, not a hash of private instructions.

Exporting an existing `Report` does not recapture its identity. Legacy/manual
reports without captured metadata export `tool: null`; their HTML/feedback says
unknown/unavailable, and SARIF omits `semanticVersion`. Existing history entries
without `tool` remain readable and are not backfilled. Existing fields and score
calculation are unchanged; JSON consumers should accept additive fields.

## Limits

This is **source identification, not a signature, security attestation or accuracy
measurement**. It hashes installed source on disk, not necessarily bytecode already
loaded in a long-lived Python process. Restart after modifying an installation;
keep both installation and repository stable during a scan. Reads are not atomic.
The manifest excludes Python itself, dependencies/build tools, package metadata,
workflows, Git revision, environment, and repository inputs/policy. A digest may be
unavailable in bytecode-only or restricted installations; scanning still proceeds
and retains the declared version.

Identical source digests do not guarantee identical results: inputs, configuration,
suppressions, Python version, OS/filesystem behavior and baseline must also match.
History summaries still compute numeric score trends across entries; changes in
tool identity or missing metadata mean a trend cannot be attributed solely to
repository improvements. Keep the raw reports and exact input/policy revisions
when investigating a difference. Frozen research protocols and their older,
separately scoped source fingerprints are not retroactively rewritten or equated
with this format.
