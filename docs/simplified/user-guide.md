# 使用指南

[English](../user-guide.md) | 简体中文 | [繁體中文](../traditional/user-guide.md) · [项目主页](../../README.simplified.md)

AgentConfigScore 是本地、确定性的编程助手指令检查器和 PR 回归门禁。它不调用 AI 服务，也不执行指令文件中的命令。100 分不代表指令有用、始终安全或比 AI 审查更好。

## 1. 安装并确认版本

需要 Python 3.10+。`diff` 需要 Git；普通目录扫描和两个目录间的 `compare` 不需要 Git。

```bash
python -m pip install agent-config-score
agent-config-score --version
agent-config-score --help
```

`acs` 是短命令别名。v0.23.0+ 支持相同功能的 `python -m agent_config_score`，不依赖主命令的 PATH 设置。旧版本没有此模块入口。查看[已发布版本](https://github.com/LE0-Lin/AgentConfigScore/releases)，不要默认认为 `main` 的改动已经进入 PyPI 或滚动 `v0` 引用。

## 2. 在自己的仓库初始化

```bash
agent-config-score init --dry-run
agent-config-score init
agent-config-score doctor
```

`init` 生成 `.agentconfigscore.json` 和 `.github/workflows/agent-config-score.yml`，不创建或改写指令文件。已有冲突文件默认不覆盖；使用 `--force` 前先检查。与生成内容相同的重复初始化不会改动文件。

审核后提交生成的配置和工作流。只想本地使用时选 `init --no-workflow`；标准工作流缺失会成为 doctor 的提示性警告，而不是错误。

若没有找到支持的指令文件，请编写符合仓库实际情况的指令，或采用[模板（英文）](../../examples/README.md)。不要仅为涨分添加词句。[完整发现范围（英文）](../../README.md#what-it-scans)。

## 3. 检查当前目录

```bash
agent-config-score .
agent-config-score rules
agent-config-score rules curl-pipe-shell
```

普通扫描默认报告发现，不因为有发现就自动阻止后续操作。需要绝对分数门槛时，在策略中设置 `fail_under` 或明确传入：

```bash
agent-config-score . --fail-under 90
```

仓库不必先达到 90 分才能采用回归门禁。请结合规则、位置、上下文审核结果，不要把分数当成总体质量排名。

## 4. 推送前检查改动

```bash
agent-config-score diff
```

包括未提交的工作区改动。尽可能采用本地已有的安全默认分支基线，不自动 fetch。也可明确指定：

```bash
agent-config-score diff origin/main
```

如果引用不存在，请自己获取该分支。应选择项目真正的默认分支，而非已经包含改动的功能分支。浅克隆需要足够的历史；生成的 Actions 工作流使用 `fetch-depth: 0`。

没有 Git 时，可以比较两个已存在的目录：

```bash
agent-config-score compare ../repo-base . --max-drop 0 --fail-on-new-errors
```

两侧均使用基线策略和豁免。候选改动不能通过提高自己的降分预算或豁免新错误来批准自己；可信调用方的命令行覆盖必须明确传入。

v0.24.0+ 仅豁免同一目录内、一对一匹配、文本完全相同且目标为新增文件的移动；现存副本或把根目录规则搬入子目录不能掩盖删除。对比复用扫描时读取的文本，不再重新打开指令文件；请保持两侧目录稳定，编辑后重新检查。[回归覆盖范围（英文）](../regression-coverage.md)。两边都是 `100` 分仍可能有回归专用错误；上面的示例启用了新错误阻断，没有策略的裸 CLI 默认仍只检查降分。

## 5. 理解失败并处理

- `diff` / `compare` 返回 `1`：配置的回归门禁未通过。检查新发现与允许的降分幅度，处理实际指令问题。
- 疑似误报仍需审核。接受的例外可以使用经基线审核的豁免，填写稳定规则 ID、原因、到期日期；结果保留审计记录。[豁免细节（英文）](../../README.md#auditable-exceptions)。
- 返回 `2`：检查无法完成，如配置无效、Git 引用缺失、报告不可写。**这不是干净的结果**，不能因为没有 JSON 就批准改动。

| 命令 | 返回 0 | 返回 1 | 返回 2 |
|---|---|---|---|
| 扫描（`agent-config-score .`） | 扫描完成，满足可选门槛 | 低于设置的分数门槛 | 输入无效或操作错误 |
| `diff`、`compare` | 基线策略通过 | 新错误或降分门禁未通过 | 无法完成比较 |
| `doctor` | 无错误项，可能有警告 | 有错误检查项 | 参数或调用错误 |
| 其他命令 | 请求的操作完成 | 不是 lint 门禁 | 输入无效或操作错误 |

意外的程序错误不会被通用异常捕获隐藏。分享堆栈前先删除私密信息；回归测试通过并不保证程序没有 bug。

## 6. 在本地保存报告

```bash
agent-config-score . --json
agent-config-score . --html .agent-config-score/report.html --badge .agent-config-score/badge.svg --sarif .agent-config-score/results.sarif
agent-config-score diff --markdown .agent-config-score/regression.md
```

不要把报告放在会被当成指令文件扫描的位置。JSON、HTML、SARIF 和回归报告可能包含仓库路径及发现信息，分享前先检查。输出路径不要选成源码或策略文件，避免覆盖。多个报告写入不是事务：后一个写入失败时，前一个报告可能已生成。

v0.24.0+ 还会在 JSON、HTML、SARIF 和新的历史快照中保留声明版本及尽力读取的工具源码 SHA-256；`compare` / `diff` JSON 分别保留两次扫描的身份。它用于区分同版本号的不同实现，本身不证明准确率或可复现性。工具源码缺失时指纹不可用，但不使扫描失效。覆盖范围、兼容性和环境／输入限制见[报告身份说明（英文）](../report-identity.md)；不会为旧报告补标新的身份。

需要隐私最小化草稿时：

```bash
agent-config-score feedback . --output .agent-config-score/case.md
```

不会上传任何内容。请自行审核、脱敏后再分享。

## 可选：检查删除保护缺项（v0.24.0+）

```bash
agent-config-score guardrails . --file AGENTS.md
agent-config-score guardrails . --file AGENTS.md --template-language simplified --json
```

此独立命令只给出选定文件的非计分建议。“未识别到保护”表示需要审核，不等于不安全。默认预览不改文件；审核完整策略上下文和补全文本后，使用打印出的确切确认值，以同一命令加上 `--apply TOKEN` 追加。输入变化须重新预览；有歧义的标记和文件别名需手动合并。英文、简体和繁体补全文本不改变 CLI 界面语言。[语法、范围、隐私及非原子／部分写入限制（英文）](../guardrail-suggestions.md)。现有评分和 CI 默认行为不变。

明确标注的示例章节不算有效策略；如果该章节延续到文件末尾，就不能自动追加。少数明确要求跳过删除确认的句式会产生只含行号与类型的 `review_signals`，即使其他位置已识别到保护，也不能自动追加。请先手动处理这些策略；这不是通用的矛盾检测器。

尚未发布的源码可直接选择 `--file`，不先遍历整仓，因此无关指令文件的坏链接不会阻止这次单文件审阅。相关忽略规则和所选路径的祖先目录检查仍生效；目录别名或大小写有歧义的目录须手动接入。其他文件不会因此被验证或修复，普通扫描／doctor 的失败仍须单独处理；追加成功不代表整仓扫描完整或安全。此范围修正不在 v0.24.0 包中。

## 可选：面向维护者的具体建议（v0.24.0+）

```bash
agent-config-score . --explain
agent-config-score diff --explain --markdown .agent-config-score/regression.md
agent-config-score init --pr-comment --dry-run
```

`--explain` 在文本／Markdown 中为扫描的有效发现、回归比较的新增发现补充静态处理建议，不改变 JSON、评分或退出策略；不执行命令、不修复文件。[最佳实践清单（英文）](../best-practices.md)也不计分。`init --pr-comment` 显式选择生成同仓库 PR 评论工作流，并提示 `pull-requests: write` 权限；默认 `init` 生成的工作流仍只申请 GitHub 只读权限。先预览、审核，只提交一份工作流；已有冲突须主动审核，不能自动覆盖。Fork PR 保留任务摘要，不发评论。生成的 Action 引用仍为 `v0`，解释摘要需要 v0.24.0+ 或包含该功能的已验证 Action 版本。升级本地 CLI 不会改变已有工作流固定的 Action 版本。详见[维护者流程（英文）](../maintainer-workflow.md)。

仅更新 CI、不读取或重置自定义策略时（v0.24.0+）：

```bash
agent-config-score init --workflow-only --pr-comment --force --dry-run
agent-config-score init --workflow-only --pr-comment --force
```

执行第二条命令前，先将示例与已有工作流的自定义内容比较；`--force` 会替换该工作流，不会合并 YAML。策略文件不在操作范围内，即使缺失或无效也不会读取，请另行运行 `doctor`。选定目标涉及链接、reparse point 或共享文件时须手动接入。初始化会提示生成的 Action 引用，它可能与本地 CLI 版本不同，也不会更新远程引用。写入有预检，但不是原子文件系统事务。

## 常见问题

| 现象 | 检查方法 |
|---|---|
| 找不到命令 | 确认装入当前 Python 环境，并检查 Scripts/bin 的 PATH。v0.23.0+ 可用 `python -m agent_config_score`。 |
| 配置或工作流编码错误 | 保存为 UTF-8，不要用 UTF-16 文件替代。 |
| `Unable to read repository path index` | 运行 `doctor`，核对 `repository-paths` 错误并修复目录访问或 I/O 问题。部分索引不会生成成功报告。 |
| 扫描源解析或读取错误 | 在本地核对已选择的指令文件和忽略文件链接，目标必须是仓库内的普通文件；修复失效、循环链接或权限问题。`doctor` 给出 `instructions` 错误，不要把不完整扫描当成通过。 |
| 报告不可写 | 选择可写的文件路径，不是已有目录；检查父目录权限。 |
| 无法检测基线 | 运行 `doctor`，然后指定本地已有的默认分支引用。 |
| 禁止示例被报为危险指令 | 对照[支持的禁止语法（英文）](../instruction-context.md)检查具体上下文；工具不理解任意语言和改写。 |
| 旧 GitHub 运行记录是红色 | 查看当前提交对应的运行。后续修复不会抹掉历史失败记录。 |

使用前阅读[限制说明](limitations.md)。发现是审核信号，不代替代码审查或安全评估。[翻译范围](../translations.md)。
