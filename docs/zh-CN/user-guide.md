# 使用指南

[English](../user-guide.md) | 简体中文 | [繁體中文](../zh-TW/user-guide.md) · [项目主页](../../README.zh-CN.md)

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

需要隐私最小化草稿时：

```bash
agent-config-score feedback . --output .agent-config-score/case.md
```

不会上传任何内容。请自行审核、脱敏后再分享。

## 常见问题

| 现象 | 检查方法 |
|---|---|
| 找不到命令 | 确认装入当前 Python 环境，并检查 Scripts/bin 的 PATH。v0.23.0+ 可用 `python -m agent_config_score`。 |
| 配置或工作流编码错误 | 保存为 UTF-8，不要用 UTF-16 文件替代。 |
| 报告不可写 | 选择可写的文件路径，不是已有目录；检查父目录权限。 |
| 无法检测基线 | 运行 `doctor`，然后指定本地已有的默认分支引用。 |
| 禁止示例被报为危险指令 | 对照[支持的禁止语法（英文）](../instruction-context.md)检查具体上下文；工具不理解任意语言和改写。 |
| 旧 GitHub 运行记录是红色 | 查看当前提交对应的运行。后续修复不会抹掉历史失败记录。 |

使用前阅读[限制说明](limitations.md)。发现是审核信号，不代替代码审查或安全评估。[翻译范围](../translations.md)。
