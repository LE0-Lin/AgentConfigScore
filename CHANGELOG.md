# Changelog

## v0.3.0

### Added

- First-class composite GitHub Action via root `action.yml`.
- Copy-paste pull-request regression workflow using `LE0-Lin/AgentConfigScore@v0`.
- Automatic PR base-SHA resolution and temporary baseline worktree management.
- GitHub Actions Step Summary output for regression reports.
- Input validation for `base-sha`, `max-drop`, and `fail-on-new-errors`.
- Self-dogfooding workflow that runs the local action on AgentConfigScore's own pull requests.

### Changed

- README now leads with the regression-gate use case and 30-second GitHub Actions integration.
- Package version bumped to `0.3.0`.

## v0.2.0

### Added

- Baseline-to-candidate `compare` command.
- Score-delta reporting with new and resolved findings.
- `--max-drop`, `--fail-on-new-errors`, and Markdown summary output.
- Pull-request regression workflow.

## v0.1.0

### Added

- Deterministic 0–100 agent-config scoring.
- Detection for duplication, contradictions, dead paths, dangerous shell commands, and common secret patterns.
- HTML report and SVG badge generation.
