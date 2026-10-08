# AgentConfigScore

[English](README.md) | 简体中文 | [繁體中文](README.traditional.md)

为 AI 编程助手的指令文件提供本地检查与 PR 回归门禁。

![AgentConfigScore 演示](https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/main/assets/agent-config-score-demo.gif)

AgentConfigScore 检查 `AGENTS.md`、`CLAUDE.md`、Cursor、Copilot、Gemini 等配置，并比较改动前后的基线，回答一个具体问题：**这次改动是否引入了已知规则能检测到的风险？**

它是确定性检查器，不是 AI 评委。**A 100 只表示没有命中生效的规则，不表示指令有用、语义完美或安全无误。** 中文文档也不意味着检测器已经能够理解任意中文指令。

## 快速开始

需要 Python 3.10+。`diff` 还需要 Git；普通目录扫描和两个目录之间的 `compare` 不需要 Git。

```bash
python -m pip install --upgrade agent-config-score
agent-config-score --version
agent-config-score init
agent-config-score doctor
agent-config-score diff
```

在自己的仓库目录中运行。`init` 会生成 `.agentconfigscore.json` 和 `.github/workflows/agent-config-score.yml`；检查后提交这两个文件，后续 PR 即可自动检查。它不会替你编写或重写指令文件，也不会默认覆盖冲突的已有配置。

`acs` 是短命令别名。v0.23.0+ 还可以使用 `python -m agent_config_score`，避免终端 PATH 没有找到命令的问题。

- [简体中文使用指南](docs/simplified/user-guide.md)：安装、基线、报告、退出码与排错。
- [分数含义与限制](docs/simplified/limitations.md)：先了解什么能检出、什么仍可能漏掉。
- [完整英文文档索引](docs/README.md)：进阶接口与研究资料。

## 为什么采用回归检查

现有仓库不必先达到 100 分才能接入。如果基线是 72 分，没有退步的改动可以通过；降低分数或引入新错误的改动则依据配置被拦截。

初始化后的核心策略如下：

```json
{
  "$schema": "https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/v0/schema/agentconfigscore.schema.json",
  "version": 1,
  "policy": {
    "max_drop": 0,
    "fail_on_new_errors": true
  }
}
```

比较时以**基线策略**为准：PR 不能通过放宽自己的阈值，或新增自己的豁免来批准自己。需要接受某项例外时，必须经过基线审核，填写规则 ID、原因和到期日期；被豁免的发现仍保留审计记录。

普通扫描默认只报告发现，不因发现问题就自动失败。需要绝对分数门槛时显式设置：

```bash
agent-config-score . --fail-under 90
```

## 本地检查与报告

```bash
agent-config-score .
agent-config-score rules curl-pipe-shell
agent-config-score diff origin/main
agent-config-score compare ../repo-base . --max-drop 0 --fail-on-new-errors
agent-config-score . --json
agent-config-score . --html .agent-config-score/report.html --sarif .agent-config-score/results.sarif
```

`diff` 包含未提交的工作区改动，自动基线检测不联网、不自动 fetch。找不到基线时，明确指定本地已有的默认分支引用。

规则、行号和上下文比数字本身更重要。报告可能包含仓库路径和发现信息，公开分享前请检查。`feedback` 可生成隐私最小化的本地草稿，但不会上传，仍需自己审核。

## 接入 GitHub Actions

优先使用 `init` 生成工作流，也可以手工配置：

```yaml
name: agent-config-regression

on:
  pull_request:

permissions:
  contents: read

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: LE0-Lin/AgentConfigScore@v0.23.0
```

固定 `@v0.23.0` 有利于复现；`@v0` 是会随后续版本更新的滚动引用。PR 评论属于[可选集成（英文）](docs/pr-comments.md)，扫描器默认不替你发评论。

## 支持的指令文件

包括根目录和嵌套目录的 `AGENTS.md` / `AGENTS.override.md`、`CLAUDE.md`、`GEMINI.md`、Cursor 的 `.cursorrules` / `.cursor/rules/`、Copilot 的 `.github/copilot-instructions.md` / `.github/instructions/`，以及 `.claude/`、`.clinerules`、`.windsurfrules`。可使用 `.agentconfigscoreignore` 排除发现路径。

准备自己的指令文件时，可参考[复制即用模板（英文）](examples/README.md)，并替换成仓库真正的命令和约束。不要为了得高分而复制空泛的“最佳实践”。

## 可靠性与边界

运行时没有第三方依赖；本地扫描不调用 AI API，也不执行指令文件中的命令。包安装需要访问所选软件包索引；GitHub Actions 是单独的 CI 环境，报告访问权限由你的工作流控制。

跨平台测试、维护的规则用例和安装验收证明程序符合指定的工程预期，**不证明它比直接问 AI 更准，也不证明它已经有真实用户价值**。独立对照评测尚未完成，已知语义漏报仍保留。详见[限制说明](docs/simplified/limitations.md)与[评测资料（英文）](benchmarks/README.md)。

本页是核心入门的中文概览，不是完整英文 README 的逐行翻译。使用指南和限制说明已提供中文；高级 Action 参数、规则语法细节、贡献及研究文档目前仍为英文。[翻译范围与维护说明](docs/translations.md)。命令、终端消息和 JSON 协议保持原样，English 仍是默认入口。

项目采用 [MIT 协议](LICENSE)。[发布与升级说明](docs/releases/v0.23.0.md)目前为英文。
