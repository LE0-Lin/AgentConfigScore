# 使用指南

[English](../user-guide.md) | [简体中文](../simplified/user-guide.md) | 繁體中文 · [專案首頁](../../README.traditional.md)

AgentConfigScore 是在本機執行、結果確定的開發助手指令檢查工具與 PR 回歸檢查。它不呼叫 AI 服務，也不執行指令檔內的命令。100 分不代表指令實用、始終安全或優於 AI 審查。

## 1. 安裝並確認版本

需要 Python 3.10+。`diff` 需要 Git；一般目錄掃描和兩個目錄之間的 `compare` 不需要 Git。

```bash
python -m pip install agent-config-score
agent-config-score --version
agent-config-score --help
```

`acs` 是較短的命令別名。v0.23.0+ 支援相同功能的 `python -m agent_config_score`，不依賴主命令的 PATH 設定。舊版本沒有此模組入口。請查看[已發布版本](https://github.com/LE0-Lin/AgentConfigScore/releases)，不要假設 `main` 的改動已經出現在 PyPI 或滾動 `v0` 參照。

## 2. 在自己的儲存庫初始化

```bash
agent-config-score init --dry-run
agent-config-score init
agent-config-score doctor
```

`init` 建立 `.agentconfigscore.json` 和 `.github/workflows/agent-config-score.yml`，不建立或改寫指令檔。既有衝突檔案預設不覆寫；使用 `--force` 前請先檢查。若內容與產生的設定相同，重複初始化不會改動檔案。

審閱後提交產生的設定與工作流程。只想在本機使用時選 `init --no-workflow`；缺少標準工作流程只會成為 doctor 的提示性警告，不是錯誤。

若沒有找到支援的指令檔，請撰寫符合儲存庫實際需求的指令，或使用[範本（英文）](../../examples/README.md)。不要只為提高分數添加詞句。[完整探索範圍（英文）](../../README.md#what-it-scans)。

## 3. 檢查目前目錄

```bash
agent-config-score .
agent-config-score rules
agent-config-score rules curl-pipe-shell
```

一般掃描預設回報結果，不會只因有發現就自動阻擋後續操作。需要絕對分數門檻時，在策略中設定 `fail_under` 或明確傳入：

```bash
agent-config-score . --fail-under 90
```

儲存庫不必先達到 90 分才能導入回歸檢查。請依規則、位置與上下文審閱結果，不要把分數當成整體品質排名。

## 4. 推送前檢查改動

```bash
agent-config-score diff
```

包含尚未提交的工作目錄改動。盡可能使用本機已存在的安全預設分支基準，不會自動 fetch。也能明確指定：

```bash
agent-config-score diff origin/main
```

如果參照不存在，請自行取得該分支。應選專案真正的預設分支，而不是已經包含改動的功能分支。淺層複製需要足夠的歷史；產生的 Actions 工作流程使用 `fetch-depth: 0`。

沒有 Git 時，可以比較兩個已存在的目錄：

```bash
agent-config-score compare ../repo-base . --max-drop 0 --fail-on-new-errors
```

兩側都套用基準策略與排除設定。候選改動不能藉由增加自己的降分預算或排除新錯誤來核准自身；受信任呼叫端若要覆寫命令列設定，必須明確傳入。

## 5. 理解失敗並處理

- `diff` / `compare` 返回 `1`：設定的回歸檢查未通過。檢查新增發現與允許的降分幅度，處理實際指令問題。
- 疑似誤報仍須審閱。接受的例外可以使用經基準審查的排除設定，指定穩定規則 ID、原因與到期日；結果仍保留稽核紀錄。[例外細節（英文）](../../README.md#auditable-exceptions)。
- 返回 `2`：檢查無法完成，例如設定無效、Git 參照不存在或報告無法寫入。**這不是乾淨的結果**，不能因為沒有 JSON 就核准改動。

| 命令 | 返回 0 | 返回 1 | 返回 2 |
|---|---|---|---|
| 掃描（`agent-config-score .`） | 掃描完成，符合選用門檻 | 低於設定的分數門檻 | 輸入無效或操作錯誤 |
| `diff`、`compare` | 基準策略通過 | 新錯誤或降分檢查未通過 | 無法完成比較 |
| `doctor` | 無錯誤項目，可能有警告 | 有錯誤檢查項目 | 參數或呼叫錯誤 |
| 其他命令 | 要求的操作完成 | 不是 lint 門檻檢查 | 輸入無效或操作錯誤 |

非預期的程式錯誤不會被通用例外處理隱藏。分享堆疊資訊前請移除私人內容；回歸測試通過不保證程式沒有 bug。

## 6. 在本機儲存報告

```bash
agent-config-score . --json
agent-config-score . --html .agent-config-score/report.html --badge .agent-config-score/badge.svg --sarif .agent-config-score/results.sarif
agent-config-score diff --markdown .agent-config-score/regression.md
```

不要將報告放在會被視為指令檔掃描的位置。JSON、HTML、SARIF 與回歸報告可能包含儲存庫路徑和檢查資訊，分享前請先檢查。輸出路徑不要選擇原始碼或策略檔案，以免覆寫。多份報告寫入不是交易：後一份寫入失敗時，前一份可能已經產生。

需要盡量減少私人資訊的草稿時：

```bash
agent-config-score feedback . --output .agent-config-score/case.md
```

不會上傳任何內容。請自行審閱並移除敏感資訊後再分享。

## 常見問題

| 現象 | 檢查方法 |
|---|---|
| 找不到命令 | 確認安裝在目前 Python 環境，並檢查 Scripts/bin 的 PATH。v0.23.0+ 可用 `python -m agent_config_score`。 |
| 設定或工作流程編碼錯誤 | 儲存為 UTF-8，不要以 UTF-16 檔案取代。 |
| 報告無法寫入 | 選擇可寫入的檔案路徑，不是既有目錄；檢查父目錄權限。 |
| 無法偵測基準 | 執行 `doctor`，再指定本機已存在的預設分支參照。 |
| 禁止範例被判為危險指令 | 對照[支援的禁止語法（英文）](../instruction-context.md)檢查上下文；工具不理解任意語言和改寫。 |
| 舊 GitHub 執行紀錄是紅色 | 查看目前提交對應的執行結果。後續修正不會抹除歷史失敗紀錄。 |

使用前閱讀[限制說明](limitations.md)。發現是審查訊號，不代替程式碼審查或安全評估。[翻譯範圍](../translations.md)。
