# Documentation

[English](user-guide.md) | [简体中文](zh-CN/user-guide.md) | [繁體中文](zh-TW/user-guide.md)

Start with the [user guide](user-guide.md): install, initialize, check a change,
read the result, and troubleshoot a failing gate.

## Using the tool

- [User guide and exit codes](user-guide.md)
- [Visual tour](visual-tour.md)
- [Instruction templates](../examples/README.md)
- [Repository doctor](doctor.md)
- [Optional PR comments](pr-comments.md)
- [Score-history workflow](score-history.md) and [local history command](score-history-cli.md)
- [Policy and suppression schema](../schema/agentconfigscore.schema.json)

## Understanding findings

- [Score contract and limitations](limitations.md)
- [Instruction context and prohibition scopes](instruction-context.md)
- [False success-reporting checks](verification-reporting.md)
- [Bulk environment-transfer checks](environment-upload.md)

Use `agent-config-score rules` for the installed version's actual catalog, and
`agent-config-score rules RULE_ID` for an individual rule's evidence and penalty.

## Development and evidence

- [Release acceptance and localization sequence](release-readiness.md)
- [Maintained benchmarks](../benchmarks/README.md)
- [AI-comparison protocol and limitations](review-comparison.md)
- [Unreviewed prospective corpus](../benchmarks/prospective-review-v1/README.md)
- [Changelog](../CHANGELOG.md), [contribution guide](../CONTRIBUTING.md), and [license](../LICENSE)

Research preparations are separate from the product's installation and CI path.
They do not need to complete before you can use the deterministic regression
gate, and they do not establish its real-world accuracy.
