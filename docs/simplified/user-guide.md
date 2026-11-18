# 使用指南

[English](../user-guide.md) | 简体中文 | [繁體中文](../traditional/user-guide.md) · [项目主页](../../README.simplified.md)

AgentConfigScore 是本地运行的确定性编程助手指令检查器和 PR 回归门禁。它不调用 AI 服务，不执行指令文件中的命令，也不是文件系统沙箱。100 分只表示没有命中生效规则，不代表指令完整或绝对安全。

如果想直观对比“单纯看分数变化”与“基线新错误门禁”的区别，可以在源码仓库中运行[回归设计演示（英文）](../../examples/regression-lab/README.md)。

## 1. 安装

需要 Python 3.10+。`diff` 还需要 Git；普通目录扫描和 `compare` 不需要 Git。

```bash
python -m pip install agent-config-score
agent-config-score --version
agent-config-score --help
```

也可以用短别名 `acs`，或在 `PATH` 未配置时直接运行 `python -m agent_config_score`。PyPI 与 `main` 分支的差异请以[已发布版本](https://github.com/LE0-Lin/AgentConfigScore/releases)为准。

## 2. 初始化仓库

```bash
agent-config-score init --dry-run
agent-config-score init
agent-config-score doctor
```

`init` 会生成 `.agentconfigscore.json` 和 `.github/workflows/agent-config-score.yml`，不会改动你的指令文件。已有冲突文件默认不覆盖（需要显式加 `--force`），内容一致时重复运行不会修改文件。审核后提交生成的文件即可；如果只需要本地检查，使用 `init --no-workflow`。

配置注意事项：

- `.agentconfigscore.json` 必须是严格有效的 JSON（不允许重复键名、`NaN`/`Infinity` 或布尔类型 `version`），且必须解析为仓库根目录内的普通文件。文件缺失时回退到默认值；损坏、失效链接或越界配置会直接返回退出码 `2`（`doctor` 返回 `1`）。
- 详见[配置解析与边界（英文）](../doctor.md#configuration-decoding)。
- 若 `doctor` 未发现支持的指令文件，可按仓库实际情况编写，或参考[模板（英文）](../../examples/README.md)与[扫描范围（英文）](../../README.md#what-it-scans)。

## 3. 本地扫描

```bash
agent-config-score .
agent-config-score rules
agent-config-score rules curl-pipe-shell
```

普通扫描默认只输出发现项并返回 `0`。如需绝对分数门槛，可在 `.agentconfigscore.json` 中设置 `fail_under` 或通过命令行传入：

```bash
agent-config-score . --fail-under 90
```

不必先把仓库做到 90 分再接入 PR 回归门禁。请结合规则 ID、位置和上下文查看结果，不要把分数当成总体质量排名。

## 4. 推送前检查改动

```bash
agent-config-score diff
```

`diff` 会把当前工作区（含未提交改动）与本地已有的默认分支对比，不会自动 `git fetch`。也可显式指定基线引用：

```bash
agent-config-score diff origin/main
```

浅克隆仓库请先拉取足够历史（生成的 GitHub Actions 工作流默认使用 `fetch-depth: 0`）。没有 Git 时可直接对比两个目录：

```bash
agent-config-score compare ../repo-base . --max-drop 0 --fail-on-new-errors
```

两侧统一使用**基线**的策略与豁免，因此候选 PR 无法靠调低自身阈值或给自己加豁免来放行。迁移指令文件只有在“同目录、一对一、原文完全一致、目标为新增支持文件”时才不会触发 `instruction-file-removed`（详见[回归覆盖范围（英文）](../regression-coverage.md)）。

## 5. 退出码与处理方式

- **返回 `1`（`diff` / `compare`）**：未通过回归门禁。修复指令改动；若确认属于合理例外，则在基线配置中添加带规则 ID、原因和到期日的豁免（[可审计豁免（英文）](../../README.md#auditable-exceptions)）。
- **返回 `2`**：运行失败（配置错误、Git 引用缺失、文件不可读、报告不可写等）。**切勿把退出码 `2` 当成通过。**

| 命令 | 返回 0 | 返回 1 | 返回 2 |
|---|---|---|---|
| 扫描（`agent-config-score .`） | 扫描完成，满足可选门槛 | 低于设置的分数门槛 | 输入无效或运行失败 |
| `diff`、`compare` | 基线策略通过 | 新错误或降分门禁未通过 | 无法完成比较 |
| `doctor` | 无错误项（允许警告） | 存在错误项 | 参数或调用错误 |
| `scope` | 建议性分析完成 | 不使用 | 输入无效或读取失败 |
| `scope compare`、`scope diff`、`scope coverage` | 分析完成或已启用门禁通过 | 已启用的丢失／未知门禁触发 | 输入、读取或限额错误 |
| 其他命令 | 操作完成 | 不使用 | 输入无效或运行失败 |

## 6. 在本地保存报告

```bash
agent-config-score . --json
agent-config-score . --html .agent-config-score/report.html --badge .agent-config-score/badge.svg --sarif .agent-config-score/results.sarif
agent-config-score diff --markdown .agent-config-score/regression.md
```

请把报告写到不会被当成指令文件扫描的位置。JSON、HTML、SARIF 和 Markdown 报告可能包含仓库路径和发现信息，对外分享前请先检查。每份报告都会记录工具版本与源码 SHA-256 指纹（[报告身份（英文）](../report-identity.md)）。

本地历史索引损坏时，`history` 会直接返回 `2` 而不会悄悄重置数据（[本地历史与恢复（英文）](../score-history-cli.md)）。

如需生成隐私最小化的问题草稿（不会自动上传）：

```bash
agent-config-score feedback . --output .agent-config-score/case.md
```

## 可选：删除保护检查

```bash
agent-config-score guardrails . --file AGENTS.md
agent-config-score guardrails . --file AGENTS.md --template-language simplified --json
```

`guardrails` 只检查单个指定文件是否包含删除确认保护语句，不计分，也不会触发整仓扫描。默认仅预览建议文本；确认无误后用输出的 `--apply TOKEN` 追加（令牌与当前文件内容绑定）。示例章节、HTML 标记或冲突的绕过语句需要手动合并，详见[删除保护建议（英文）](../guardrail-suggestions.md)。

## 可选：Cursor 文件上下文与覆盖检查

```bash
agent-config-score scope . --target src/web/app.ts
agent-config-score scope . --target src/web/app.ts --target src/api/service.py --json
```

`scope` 根据声明的目标路径静态预测根目录 `.cursor/rules/` 的自动加载情况（不计分，手动／模型选择规则保持 `unknown`，详见[模型与限制（英文）](../cursor-scope.md)和[运行示例（英文）](../../examples/cursor-scope/README.md)）。

对比同一上下文的改动前后变化，或逐个检查目录下所有普通文件：

```bash
agent-config-score scope compare ../repo-base . --target src/web/app.ts --fail-on-lost-directives --fail-on-unknown
agent-config-score scope diff origin/main --target src/web/app.ts --fail-on-lost-directives --fail-on-unknown --json
```

```bash
agent-config-score scope coverage --base-ref origin/main --under src --fail-on-lost-directives --fail-on-unknown --json
```

不加 `--fail-on-*` 时为建议模式（返回 `0`）；加上后，基线生效指令丢失或出现未知规则会返回 `1`。详见[范围对比（英文）](../cursor-scope-impact.md)、[逐文件覆盖（英文）](../cursor-coverage.md)和[四个对照示例（英文）](../../examples/cursor-scope-impact/README.md)。

## 可选：`--explain` 与 PR 评论

```bash
agent-config-score . --explain
agent-config-score diff --explain --markdown .agent-config-score/regression.md
agent-config-score init --pr-comment --dry-run
```

`--explain` 在文本和 Markdown 输出中附带静态处理建议，不改变分数、JSON 或退出码（另见不计分的[最佳实践清单（英文）](../best-practices.md)）。`init --pr-comment` 会生成带 `pull-requests: write` 权限的同仓库 PR 评论工作流（Fork PR 仍只输出只读任务摘要）。详见[维护者流程（英文）](../maintainer-workflow.md)。

如需只更新 CI 工作流而不触碰 `.agentconfigscore.json`：

```bash
agent-config-score init --workflow-only --pr-comment --force --dry-run
agent-config-score init --workflow-only --pr-comment --force
```

`--force` 会整体替换工作流文件（不会合并 YAML）；请先核对已有自定义配置，并单独运行 `doctor` 验证策略。

## 常见问题

| 现象 | 检查方法 |
|---|---|
| 找不到命令 | 确认当前 Python 环境的 `Scripts`/`bin` 在 `PATH` 中，或改用 `python -m agent_config_score`。 |
| 配置或工作流编码错误 | 保存为 UTF-8，不要使用 UTF-16。 |
| 报告无法写入 | 选择可写文件路径（不是已有目录），并检查父目录权限。 |
| `Unable to read repository path index` | 运行 `doctor`，按 `repository-paths` 错误排查不可读目录。 |
| 扫描源解析或读取错误 | 检查指令文件与忽略文件的符号链接，目标必须是仓库内的普通文件（`doctor` 会报 `instructions`）。 |
| `diff` 无法检测基线 | 运行 `doctor`，然后显式指定本地已有的默认分支引用。 |
| 禁止示例被报为危险指令 | 对照[支持的禁止语法（英文）](../instruction-context.md)核对上下文。 |
| 旧 GitHub 运行记录为红色 | 查看最新提交对应的运行；后续修复不会清除历史失败记录。 |

用作 CI 门禁前请先阅读[限制说明](limitations.md)。[翻译范围](../translations.md)。
