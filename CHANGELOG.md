# Changelog

## v0.9.0

### Added

- Stable rule catalog with one metadata source for rule ID, severity, scoring category, penalty, summary, and description.
- `agent-config-score rules` for human-readable rule discovery.
- `agent-config-score rules RULE_ID` for detailed rule explanations.
- JSON rule-catalog output for scripts and future policy tooling.
- Catalog integrity tests covering scanner and SARIF metadata alignment.

### Changed

- Scanner pattern rules now reference shared catalog metadata instead of duplicating severity, penalty, and message fields.
- Scoring category caps are centralized with the rule catalog.
- SARIF rule descriptions, categories, severities, and penalties are generated from the shared catalog.
- The rule-catalog refactor is score-neutral for existing findings.
- Package version bumped to `0.9.0`.

## v0.8.0

### Added

- Safe one-command repository setup via `agent-config-score init`.
- Generated `.agentconfigscore.json` with conservative regression defaults.
- Generated GitHub Actions workflow using `LE0-Lin/AgentConfigScore@v0`.
- `--dry-run`, `--force`, and `--no-workflow` initialization options.
- Atomic preflight behavior: conflicts are detected before any files are written.
- Idempotent setup when generated files already match.
- Test coverage for creation, conflicts, force overwrite, policy-only setup, dry-run, idempotency, and CLI output.

### Changed

- Top-level help now includes the `init` onboarding workflow.
- Package version bumped to `0.8.0`.

## v0.7.1

### Added

- `agent-config-score --version` / `-V`.
- Top-level CLI help that advertises scan, Git-native `diff`, and directory `compare` workflows.
- GitHub Action log output that states whether the run is using baseline `.agentconfigscore.json` or compatibility defaults.
- CLI tests for version and top-level help output.

### Changed

- Package version bumped to `0.7.1`.

## v0.7.0

### Added

- Repository-level policy configuration via `.agentconfigscore.json`.
- Versioned policy schema with `max_drop`, `fail_on_new_errors`, and `fail_under` settings.
- Strict validation for malformed JSON, unknown keys, invalid types, and out-of-range thresholds.
- Baseline-governed regression policy: a candidate PR can change future policy but cannot weaken the gate that evaluates itself.
- Candidate policy validation so broken configuration is caught before merge.
- Repository policy dogfooding in AgentConfigScore's own CI.

### Changed

- Explicit CLI flags override repository policy when provided.
- The reusable GitHub Action uses baseline repository policy when present while preserving its historical defaults for repositories without a policy file.
- Package version bumped to `0.7.0`.

## v0.6.0

### Added

- Git-aware local regression checks via `agent-config-score diff BASE_REF`.
- Automatic detached baseline worktree creation and cleanup.
- Support for comparing a local branch, tag, or commit against the current working tree, including uncommitted agent-config changes.
- Clear offline error messages for missing Git refs instead of fetching implicitly.
- Test coverage for dirty working trees, nested repository paths, missing refs, non-Git directories, CLI JSON/exit behavior, and worktree cleanup.

### Changed

- Local regression checks no longer require users to manually prepare two repository directories.
- Package version bumped to `0.6.0`.

## v0.5.2

### Changed

- Align the package and Git tag for the Marketplace release.
- Make GitHub Release creation manual so Marketplace publication can own the release flow without an automated job pre-creating the same tag.
- Package version bumped to `0.5.2`.

## v0.5.1

### Changed

- Upgrade `actions/checkout` and `actions/setup-python` usage to the current v7 release line across the reusable action and repository workflows.
- Remove the Node 20 deprecation warnings observed on current GitHub-hosted runners.
- Package version bumped to `0.5.1`.

## v0.5.0

### Added

- SARIF 2.1.0 output via `agent-config-score --sarif FILE`.
- GitHub code-scanning compatible rule metadata, severity mapping, and file/line locations.
- Unit coverage for file-level and repository-level SARIF findings.
- CI validation that generates and parses a real SARIF artifact on Python 3.10, 3.12, and 3.13.

### Changed

- Package version bumped to `0.5.0`.

## v0.4.0

### Added

- Structured composite-action outputs for baseline score, candidate score, score delta, new findings, new errors, and resolved findings.
- Self-dogfood assertions that validate action outputs on every pull request.

### Changed

- The reusable GitHub Action now emits machine-readable values before returning its final regression status, so downstream workflow steps can consume the result.
- Package version bumped to `0.4.0`.

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
