# One short human preannotation task

**Status: prepared, awaiting an actual annotation.** The user agreed to read one
short sample; no decision, rationale, reviewer history or correctness result is
supplied by that agreement. No second human or model has been invented.

[Read the review page](review.md). It presents the full 28-line source, the
review-needed rubric, missing-context boundaries and a three-part plain-language
answer format. Tool/model conclusions are not shown. Source text can reveal its
project; this is prediction withholding, not anonymization or certified blinding.

## Selection and provenance

The [protocol](protocol.json) selects the smallest total UTF-8 file-text input
from all five retained context candidates, using case ID to break ties. The
selected input has 1,317 bytes; the others have 43,067, 45,571, 53,695 and 149,206
bytes. This makes a first voluntary review practical, but is convenience
selection, not an independent representative sample. No scanner/model output for
this case was inspected. The AI preparer has seen its source; this disclosure
does not turn preparation into human judgment.

The source is the unchanged scikit-learn root
[AGENTS.md at a442e4bb39551feb7b0af4c00075e2cb91cf9b77](https://github.com/scikit-learn/scikit-learn/blob/a442e4bb39551feb7b0af4c00075e2cb91cf9b77/AGENTS.md),
lines 1–28, SHA-256
`1c3209d3ade6b77652d8e6cf4100494e37db123d8036deab15f778e862ea5f00`.
The [parent context corpus](../context/corpus.json) preserves provenance and the
[BSD-3-Clause notice](../context/licenses/scikit-learn--scikit-learn.txt).
Keep those materials when redistributing the readable page. The page duplicates
an existing input for readability; it is not a new independent case.

Tests bind the displayed source bytes to that corpus, its canonical one-case
packet and the recorded selection. They test preparation integrity, not human
review completion or whether an eventual answer is correct. The parent corpus,
existing Next.js pilot, frozen tool protocol and product rules are unchanged.

## Evidence not yet supplied

An actual human answer must retain the decision, rationale, missing-context
notes and declared prior exposure without an AI filling in omissions. A single
answer stays provisional. Do not call the reviewer blind merely because the
page withholds predictions, or promote the parent corpus to adjudicated labels.

This task alone cannot establish accuracy, superiority over AI, or real user
adoption. Independent adjudication, appropriately matched tool evidence and
actual model runs remain separate gates in the
[comparison workflow](../../../docs/review-comparison.md).
