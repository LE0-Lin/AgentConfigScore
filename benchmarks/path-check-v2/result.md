# Path-reference development replay

Known development inputs; no independent accuracy estimate or external user adoption claim.

| Known control | Literal | Frozen 0.26.1 | Current source |
|---|---|---|---|
| control-01 | `./CONTRIBUTING.md` | True | True |
| control-02 | `./.github/PULL_REQUEST_TEMPLATE.md` | True | True |
| control-03 | `pnpm11/` | False | False |
| control-04 | `pnpm/` | False | False |
| control-05 | `./pnpm/AGENTS.md` | True | True |
| control-06 | `packages/` | False | False |
| control-07 | `test/unit` | False | False |
| control-08 | `packages/vitest/src/runtime/` | False | False |

Vitest's declared generated output: frozen warning **True**, current warning **False**.
Producer source was checked against the retained Git tree. Upstream code was never built or executed.

Known target-removal controls detected: 3/8 frozen; 3/8 current.
Unprefixed directory names remain outside the default prose heuristic. These mutations are not natural upstream defects.

## Separate explicit-directory variants

Detected 4/4 synthetic variants after prefixing ./ to the selected literal, then removing its target.
Both the instruction spelling and target state change in these separate controls. They are not pooled with unchanged-text controls.

## Separate fresh registry

| Repository | Result | Selected candidates |
|---|---|---|
| astral-sh/uv | license_outside_allowlist | 0 |
| pydantic/pydantic | completed_source_smoke | 0 |
| fastapi/fastapi | registered_root_instruction_absent | 0 |

The fixed fresh registry produced no eligible path candidates. It supplies no fresh correctness estimate; exclusions were not replaced.
The collected document's raw scanner observations remain in JSON, without human reference labels.

## Reproduction identity

Current source: `eb83eb8abfeadd7d13a67e0cdcb0bdc83f648658ee8487458e38b88c632bab9d`.
Frozen published source: `d6b3b079d6a8ab0d870020abe5f6489b59536c5a6602e2083dfc80b0c97d1ed5`.
The changed implementation is an unreleased source build even when its package version string still says 0.26.1.

Parser matches the pre-collection freeze: False.
A later parser may replay these inputs as development data; a mismatch does not preserve first-use freshness.
Known development acceptance passed: True.
