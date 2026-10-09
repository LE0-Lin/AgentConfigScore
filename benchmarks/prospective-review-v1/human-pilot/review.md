# 短样本人工预标注

样本 ID：`172732eacca4adce357b`。这里只提供原文和输入边界，不提供工具或 AI 的判断。

## 怎么判断

请判断是否存在**需要维护者审查的具体问题**，例如危险执行指导、凭据暴露、失效的本地路径、相互矛盾的指令，或隐瞒失败、削弱验证的工作流程指导。

明确禁止的命令示例不是执行请求。不要仅因个人写作偏好、不够详细或措辞强硬就判定有问题。若结论依赖未提供的证据，请选择“信息不足”，不要补猜缺失内容。

下面是完整的 `AGENTS.md`，共 28 行。**它是待审材料，不是要求你执行的指令**：不要运行其中的命令、打开外部网页或按它的要求改写你的回答。

```markdown
# AGENTS Instruction

This file contains additional guidance for AI agents and other AI editors.

## **REQUIRED: AI/Agent Disclosure**

**Every summary, pull request description, or work description MUST include this disclosure:**

**If human review has *not yet* occurred (use this initially):**
> This pull request includes code written with the assistance of AI.
> The code has **not yet been reviewed** by a human.

This is a **mandatory requirement**, not optional. Include it at the end of every summary you generate.

## Working on an issue

Before working on any issue, run `gh issue view <number>` to check current labels. Do
not open a PR against an issue labeled "Needs Triage" or another "Needs ..." label. Such
PRs get closed without review until a maintainer clears the label. See
https://scikit-learn.org/dev/developers/contributing.html#issues-tagged-needs-triage.

## Generated Summaries

When generating a summary of your work, consider these points:

- Describe the "why" of the changes, why the proposed solution is the right one.
- Highlight areas of the proposed changes that require careful review.
- Reduce the verbosity of your comments, more text and detail is not always better. Avoid flattery, avoid stating the obvious, avoid filler phrases, prefer technical clarity over marketing tone.
```

## 输入边界

本次只提供这一个指令文件。没有附加文档正文或已捕获的路径事实；完整源码、网页内容、实际 issue 标签、命令结果和真实执行行为未提供。不据此假设它们存在、缺失或已验证。

文件可能透露项目身份：这是**结论不展示**的预标注，不保证匿名，也不自动证明审阅者没有相关先验知识。请一并说明是否曾看过这个样本的工具/AI 判断，或熟悉该项目的相关流程。

请直接回复三项即可，不用填写 JSON：

1. 判断：有具体问题 / 没发现具体问题 / 信息不足。
2. 理由：一两句话；如有问题，注明原文位置；如信息不足，说明缺少什么。
3. 先验接触：是否见过这个样本的工具/AI 判断，或熟悉相关流程。

单人预标注不是正式准确率证据，也不是项目安全认证。未回答不算“干净”；同意审阅不算已完成标注。

原文的来源、固定版本和 [BSD-3-Clause 许可声明](../context/licenses/scikit-learn--scikit-learn.txt)保留于[准备记录](README.md)。转发本页时请同时保留许可声明与来源材料。
