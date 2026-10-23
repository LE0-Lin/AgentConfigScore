# Regression input consistency and file-removal checks

The tightened behavior below is available in **v0.24.0+**. Review new removal
signals when upgrading from v0.23.0; numeric scoring and policy defaults are unchanged.

## One captured text per selected source

`diff` and `compare` now reuse the instruction text captured by each underlying
scan for removal and directive-polarity checks. They do not reopen instruction
paths after scanning. Previously that second read could silently skip an I/O
failure, see different text, or follow an alias replaced after its validated
scan read. A report could consequently miss a reversal or invent a removal.

The private scan helper shares captured text only within the comparison. Raw
source is not attached to `Report` or `RegressionReport`, their dataclass
representations, or their exported JSON. Existing finding messages and paths can
still contain repository details; ordinary reports are not privacy-minimized.

Initial discovery, resolution and source-read failures remain operational errors:
exit `2`, no success JSON or newly written success report. Sources still use the
[instruction-file boundary](limitations.md#instruction-file-filesystem-boundary).
Reusing captured text does not weaken initial source validation.

This is **not an atomic repository snapshot**. Base and head are scanned
sequentially, files are read at different times, and configuration, ignore rules
and path-existence checks have their own reads. A file changed or deleted after
capture does not retroactively alter the report's captured instructions. Keep
both trees stable during comparison and rerun after changes. No complete input
snapshot, concurrent-change detector or security attestation is claimed.

## Narrow exact-text move exception

`instruction-file-removed` is an error-level, regression-only review signal.
A disappeared supported filename is exempt only when:

- A **newly added** supported filename in the **same repository-relative parent
  directory** has the same nonempty captured decoded text.
- That new file has not already paired with another removal. Matching is
  one-to-one, with removed paths processed in sorted order.

Normal text reading converts line endings to LF, so CRLF versus LF alone does
not prevent a match. Spaces, indentation, blank lines and literal/code-block
whitespace are otherwise significant. This compares decoded text, not raw bytes;
instruction decoding retains the scanner's existing UTF-8 replacement behavior.

An existing duplicate is not a move destination. Neither is a modified filename
that already existed in the baseline. One new file cannot excuse deletion of
two old files. Moving a root instruction into a subtree, moving between sibling
directories, or moving a nested instruction to the root still reports the old
filename's removal. Changed directory applicability must be reviewed, not assumed
equivalent merely because the words match.

This remains a **filename-coverage heuristic**, not full agent-scope analysis.
Same-directory root `CLAUDE.md` to `AGENTS.md` migrations retain their existing
exact-text exception; agent consumers, format semantics, override precedence and
frontmatter/glob applicability are not certified equivalent. Legitimate
cross-directory migrations or content merges may therefore need a reasoned,
expiring, baseline-reviewed suppression. The candidate cannot grant its own
exception. No new rule ID, numeric penalty, suppression format or policy default
is introduced.

## A high score is not the regression gate

The scan scores for both sides may still be `100` while a removal or exact
directive reversal appears in `new_findings`. Regression-only rules do not
change standalone numeric scores. Enable `policy.fail_on_new_errors` in the
trusted baseline or pass `--fail-on-new-errors` to block them with exit `1`.
`init` generates that baseline policy; the Action uses it and defaults to new-error
blocking when no policy exists. The bare CLI without a policy remains score-only
by default; this compatibility default has not silently changed.

Tests include synthetic read-error/replacement cases, external-link replacement,
literal-whitespace controls, one-to-one move matching, scoped moves, retained
same-directory moves, privacy and baseline suppression. Installed-package
acceptance checks scoped removal and existing-copy deletion with the actual
baseline gate. These are development regressions, not independent real-world
accuracy measurements or user feedback.
