# 使用指南

[English](../user-guide.md) | [简体中文](../simplified/user-guide.md) | 繁體中文 · [專案首頁](../../README.traditional.md)

AgentConfigScore 是在本機執行的確定性程式開發助手指令檢查器與 PR 回歸門禁。它不呼叫 AI 服務，不執行指令檔內的命令，也不是檔案系統沙箱。100 分只表示沒有命中生效規則，不代表指令完整或絕對安全。

若想直觀對比「只看分數變化」與「基準新錯誤門禁」的差異，可在原始碼儲存庫中執行[回歸設計示範（英文）](../../examples/regression-lab/README.md)。

## 1. 安裝

需要 Python 3.10+。`diff` 還需要 Git；一般目錄掃描和 `compare` 不需要 Git。

```bash
python -m pip install agent-config-score
agent-config-score --version
agent-config-score --help
```

也可以使用短別名 `acs`，或在 `PATH` 未設定時直接執行 `python -m agent_config_score`。PyPI 與 `main` 分支的差異請以[已發布版本](https://github.com/LE0-Lin/AgentConfigScore/releases)為準。

## 2. 初始化儲存庫

```bash
agent-config-score init --dry-run
agent-config-score init
agent-config-score doctor
```

`init` 會建立 `.agentconfigscore.json` 與 `.github/workflows/agent-config-score.yml`，不會改動你的指令檔。既有衝突檔案預設不覆寫（須明確加 `--force`），內容一致時重複執行不會修改檔案。審閱後提交產生的檔案即可；若只需要本機檢查，使用 `init --no-workflow`。

設定注意事項：

- `.agentconfigscore.json` 必須是嚴格有效的 JSON（不允許重複鍵名、`NaN`/`Infinity` 或布林型別 `version`），且必須解析為儲存庫根目錄內的一般檔案。檔案缺失時回退到預設值；損壞、失效連結或越界設定會直接回傳退出碼 `2`（`doctor` 回傳 `1`）。
- 詳見[設定解析與邊界（英文）](../doctor.md#configuration-decoding)。
- 若 `doctor` 未找到支援的指令檔，可依儲存庫實際情況撰寫，或參考[範本（英文）](../../examples/README.md)與[掃描範圍（英文）](../../README.md#what-it-scans)。

## 3. 本機掃描

```bash
agent-config-score .
agent-config-score rules
agent-config-score rules curl-pipe-shell
```

一般掃描預設只輸出發現項目並回傳 `0`。如需絕對分數門檻，可在 `.agentconfigscore.json` 中設定 `fail_under` 或透過命令列傳入：

```bash
agent-config-score . --fail-under 90
```

不必先把儲存庫做到 90 分再導入 PR 回歸門禁。請結合規則 ID、位置與上下文檢視結果，不要把分數當成整體品質排名。

## 4. 推送前檢查改動

```bash
agent-config-score diff
```

`diff` 會把目前工作目錄（含未提交改動）與本機既有的預設分支對比，不會自動 `git fetch`。也可明確指定基準參照：

```bash
agent-config-score diff origin/main
```

淺層複製請先拉取足夠歷史（產生的 GitHub Actions 工作流程預設使用 `fetch-depth: 0`）。沒有 Git 時可直接對比兩個目錄：

```bash
agent-config-score compare ../repo-base . --max-drop 0 --fail-on-new-errors
```

兩側統一套用**基準**的策略與排除設定，因此候選 PR 無法靠調低自身門檻或替自己加例外來放行。搬移指令檔只有在「同目錄、一對一、原文完全一致、目標為新增支援檔案」時才不會觸發 `instruction-file-removed`（詳見[回歸涵蓋範圍（英文）](../regression-coverage.md)）。

## 5. 退出碼與處理方式

- **回傳 `1`（`diff` / `compare`）**：未通過回歸門禁。修正指令改動；若確認屬於合理例外，則在基準設定中加入附規則 ID、原因與到期日的排除項目（[可稽核例外（英文）](../../README.md#auditable-exceptions)）。
- **回傳 `2`**：執行失敗（設定錯誤、Git 參照缺失、檔案無法讀取、報告無法寫入等）。**切勿把退出碼 `2` 當成通過。**

| 命令 | 回傳 0 | 回傳 1 | 回傳 2 |
|---|---|---|---|
| 掃描（`agent-config-score .`） | 掃描完成，符合選用門檻 | 低於設定的分數門檻 | 輸入無效或執行失敗 |
| `diff`、`compare` | 基準策略通過 | 新錯誤或降分門禁未通過 | 無法完成比較 |
| `doctor` | 無錯誤項目（允許警告） | 存在錯誤項目 | 參數或呼叫錯誤 |
| `scope` | 建議性分析完成 | 不使用 | 輸入無效或讀取失敗 |
| `scope compare`、`scope diff`、`scope coverage` | 分析完成或已啟用門禁通過 | 已啟用的遺失／未知門禁觸發 | 輸入、讀取或限額錯誤 |
| 其他命令 | 操作完成 | 不使用 | 輸入無效或執行失敗 |

## 6. 在本機儲存報告

```bash
agent-config-score . --json
agent-config-score . --html .agent-config-score/report.html --badge .agent-config-score/badge.svg --sarif .agent-config-score/results.sarif
agent-config-score diff --markdown .agent-config-score/regression.md
```

請把報告寫到不會被視為指令檔掃描的位置。JSON、HTML、SARIF 與 Markdown 報告可能包含儲存庫路徑與發現訊息，對外分享前請先檢查。每份報告都會記錄工具版本與原始碼 SHA-256 指紋（[報告身分（英文）](../report-identity.md)）。

本機歷史索引損壞時，`history` 會直接回傳 `2` 而不會悄悄重設資料（[本機歷史與復原（英文）](../score-history-cli.md)）。

如需產生隱私最小化的問題草稿（不會自動上傳）：

```bash
agent-config-score feedback . --output .agent-config-score/case.md
```

## 選用：刪除保護檢查

```bash
agent-config-score guardrails . --file AGENTS.md
agent-config-score guardrails . --file AGENTS.md --template-language simplified --json
```

`guardrails` 只檢查單一指定檔案是否包含刪除確認保護語句，不計分，也不會觸發全儲存庫掃描。預設僅預覽建議文字；確認無誤後用輸出的 `--apply TOKEN` 追加（權杖與目前檔案內容綁定）。範例章節、HTML 標記或衝突的繞過語句需要手動合併，詳見[刪除保護建議（英文）](../guardrail-suggestions.md)。

## 選用：Cursor 檔案上下文與覆蓋檢查

```bash
agent-config-score scope . --target src/web/app.ts
agent-config-score scope . --target src/web/app.ts --target src/api/service.py --json
```

`scope` 根據宣告的目標路徑靜態預測根目錄 `.cursor/rules/` 的自動載入情況（不計分，手動／模型選擇規則保持 `unknown`，詳見[模型與限制（英文）](../cursor-scope.md)與[執行範例（英文）](../../examples/cursor-scope/README.md)）。

對比同一上下文的改動前後變化，或逐一檢查目錄下所有一般檔案：

```bash
agent-config-score scope compare ../repo-base . --target src/web/app.ts --fail-on-lost-directives --fail-on-unknown
agent-config-score scope diff origin/main --target src/web/app.ts --fail-on-lost-directives --fail-on-unknown --json
```

```bash
agent-config-score scope coverage --base-ref origin/main --under src --fail-on-lost-directives --fail-on-unknown --json
```

不加 `--fail-on-*` 時為建議模式（回傳 `0`）；加上後，基準生效指令遺失或出現未知規則會回傳 `1`。詳見[範圍對比（英文）](../cursor-scope-impact.md)、[逐檔覆蓋（英文）](../cursor-coverage.md)與[四個對照範例（英文）](../../examples/cursor-scope-impact/README.md)。

## 選用：`--explain` 與 PR 評論

```bash
agent-config-score . --explain
agent-config-score diff --explain --markdown .agent-config-score/regression.md
agent-config-score init --pr-comment --dry-run
```

`--explain` 在文字與 Markdown 輸出中附帶靜態處理建議，不改變分數、JSON 或退出碼（另見不計分的[最佳實務清單（英文）](../best-practices.md)）。`init --pr-comment` 會產生附 `pull-requests: write` 權限的同儲存庫 PR 評論工作流程（Fork PR 仍只輸出唯讀工作摘要）。詳見[維護者流程（英文）](../maintainer-workflow.md)。

如需只更新 CI 工作流程而不觸碰 `.agentconfigscore.json`：

```bash
agent-config-score init --workflow-only --pr-comment --force --dry-run
agent-config-score init --workflow-only --pr-comment --force
```

`--force` 會整體替換工作流程檔案（不會合併 YAML）；請先核對既有自訂設定，並單獨執行 `doctor` 驗證策略。

## 常見問題

| 現象 | 檢查方法 |
|---|---|
| 找不到命令 | 確認目前 Python 環境的 `Scripts`/`bin` 在 `PATH` 中，或改用 `python -m agent_config_score`。 |
| 設定或工作流程編碼錯誤 | 儲存為 UTF-8，不要使用 UTF-16。 |
| 報告無法寫入 | 選擇可寫檔案路徑（不是既有目錄），並檢查父目錄權限。 |
| `Unable to read repository path index` | 執行 `doctor`，依 `repository-paths` 錯誤排查無法讀取的目錄。 |
| 掃描來源解析或讀取錯誤 | 檢查指令檔與忽略檔的符號連結，目標必須是儲存庫內的一般檔案（`doctor` 會報 `instructions`）。 |
| `diff` 無法偵測基準 | 執行 `doctor`，再明確指定本機既有的預設分支參照。 |
| 禁止範例被判為危險指令 | 對照[支援的禁止語法（英文）](../instruction-context.md)核對上下文。 |
| 舊 GitHub 執行紀錄為紅色 | 查看最新提交對應的執行；後續修正不會清除歷史失敗紀錄。 |

用作 CI 門禁前請先閱讀[限制說明](limitations.md)。[翻譯範圍](../translations.md)。
