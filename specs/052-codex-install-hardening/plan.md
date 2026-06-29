# Implementation Plan: Codex 安裝腳本硬化

**Branch**: `052-codex-install-hardening` | **Date**: 2026-06-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/052-codex-install-hardening/spec.md`

## Summary

讓一鍵安裝對「已經有 Codex 登入/設定」的使用者也能可靠成功：動檔前**先帶時間戳備份** `config.toml` + `auth.json`（備份失敗 fail-loud 中止）→ **config.toml 整檔覆寫**成乾淨平台設定（消除未知殘留，靠備份還原）→ **auth.json 以 Codex 自身 CLI 重設**（`codex logout` 再 `codex login --with-api-key`，清殘留登入優先權）→ 安裝卡與腳本**提醒先關閉執行中的 Codex 桌面版**（含 Windows 工作列常駐）。改動面＝後端安裝模板（sh/ps1）+ 前端安裝卡；無後端邏輯/DB/套件變更。真機三平台驗收（SC-006）為門檻。

## Technical Context

**Language/Version**: 後端安裝模板 POSIX `sh` + Windows PowerShell（由 `src/ai_api/api/install.py` 以 `__BASE_URL__` 取代後輸出）；前端 TypeScript + React（安裝卡）。Python 後端**邏輯不動**（只改模板字串）。
**Primary Dependencies**: 無新增。腳本用 `curl`/`python3`（sh）、`Invoke-WebRequest`（ps1）、`codex` CLI（既有）。
**Storage**: N/A（只動使用者本機 `~/.codex/{config.toml,auth.json}`；無平台 DB / migration）。
**Testing**: 既有 install contract 測試（渲染 + 內容斷言 + `sh -n`）；新增/更新斷言備份/ logout / 覆寫 / 提醒。SC-006 三平台真機為人工驗收。
**Target Platform**: 使用者本機 macOS / Linux（sh）、Windows（ps1）。
**Project Type**: web（後端模板 + 前端卡 → 兩個 image 都要 rebuild）。
**Constraints**: 動檔前必先備份（FR-002）；不無聲破壞（FR-003 以「備份+告知」滿足覆寫路徑）；fail-loud（FR-006）；冪等（FR-007）；三平台一致（FR-008）。
**Scale/Scope**: 2 個模板 + 1 張卡 + 對應 install 測試。

## Constitution Check

- **I. Test-First**：✅ 先更新 install contract 測試（斷言：備份步驟、logout 早於 login、config 為乾淨覆寫、桌面版提醒文字、fail-soft 仍在）→ 再改模板。SC-006 真機補人工。
- **II. 契約優先**：N/A（安裝腳本非對外 API 契約）。
- **III. 整合測試覆蓋外部依賴**：✅ 與 `codex` CLI（logout/login）的真實邊界以**真機驗收**覆蓋——`logout` 行為無法在 CI 完整 mock（呼應「採用前真機驗證、別硬編工具格式」）。
- **IV. 可觀測性**：✅ 腳本 echo 備份位置 + 還原方式 + 提醒 + fail-loud 錯誤訊息。
- **V. 簡潔優先（YAGNI）**：✅ 桌面版只「提醒」不自動偵測（行程名跨版本脆弱）；無新套件；config 用整檔覆寫而非為未知鍵寫一堆 surgical 規則。

**結論**：無違反、無 Complexity Tracking、Technical Context 無 NEEDS CLARIFICATION（Codex 內部不確定項已在 research 以「真機驗收」收斂，非規格層阻塞）。

## Phase 0：研究（research.md）

- **R1 — config.toml 策略：備份 + 整檔覆寫**（非 surgical 合併）。Rationale：blind（不能先探 Codex）下，整檔重設為已知乾淨狀態可繞過**所有未知殘留**（舊 `model`/登入偏好/衝突 provider）；維護者亦提此案；備份保可還原。Alternatives：surgical 合併——否決（無法枚舉未知衝突鍵，blind 下不可靠）。原 merge 正是「保留殘留 → 連不上」的根源。
- **R2 — auth.json：`codex logout` → `codex login --with-api-key`**（+ 先備份）。Rationale：清掉殘留登入（ChatGPT/OAuth）的優先權；用 Codex 自身 CLI 寫 auth、**不手寫其 JSON 格式**（跨版本會爛——experience「別硬編外部工具格式、用它的 CLI」）。`logout` 失敗即略過（安全 no-op）。Alternatives：手寫覆蓋 auth.json——否決。
- **R3 — 桌面版執行中：只「提醒」不自動偵測**。Rationale：`curl|sh` 無法中途暫停等使用者關 App；桌面版行程名跨版本/平台脆弱、偵測 CP 值低；維護者明指「提醒使用者」。卡為主（執行前先讀到）、腳本 echo 為輔。Alternatives：偵測行程暫停——列為可選後續。
- **R4 — 備份：帶時間戳 + fail-loud**。`*.bak-<YYYYMMDD-HHMMSS>`（重跑不覆蓋舊備份）；備份不可寫即中止、不在沒備份下改檔（FR-002/006）。
- **R5 — 卡文案誠實**：現有卡「CLI…保留你其他設定」在改成覆寫後**變成錯的**，必須改為「已備份、可還原」（呼應「對外設定文案要與實際行為一致」教訓——這次主動避免）。

## Phase 1：設計與契約

- **data-model.md**：不需要（無資料模型；只動本機檔 + 模板/卡文案）——於 tasks 直接列檔案改動。
- **contracts/**：不需要（非對外 API；安裝腳本行為以 install contract 測試 + 真機驗收約束）。
- **quickstart.md**：可選——三平台真機驗收步驟（既有登入 → 一鍵安裝 → 不清檔可用 + 備份可還原 + 桌面版提醒）。tasks 內以 SC-006 任務承載即可。
- **agent context**：無新技術，免跑。

## Project Structure

```text
src/ai_api/install/
├── codex.sh.tmpl       # 【改】備份+提醒（頂部）；step2 merge→clean 覆寫；step4 login 前 codex logout；結尾還原提示
└── codex.ps1.tmpl      # 【改】同上（PowerShell 版）

frontend/src/components/
└── codex-install-card.tsx  # 【改】顯眼「先關閉桌面版（含工作列常駐）」提醒；details 文案改為「已備份可還原」（修掉「保留你其他設定」的錯述）

tests/
└── （install contract 測試）# 【改】斷言備份/ logout/ 覆寫/ 提醒；既有 fail-soft 與 PowerShell 提示斷言維持
```

**Structure Decision**: 沿用既有結構。後端只改兩個 `.tmpl`（`install.py` 邏輯不動）→ 重建 **backend** image；前端改卡 → 重建 **frontend** image；兩者一起 bump。

## Complexity Tracking

> 無 Constitution 違反，無需填寫。
