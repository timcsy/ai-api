# 001：LiteLLM 形態從 Proxy Server 到 library-only
> 日期：2026-05-25

## 轉移
- 舊（superseded）：001 research §1 決定用 **LiteLLM Proxy Server**（`litellm[proxy]`），前置加 FastAPI
  攔截層；**明確評估並否決** library 模式（理由「等於自行寫 proxy、失去 LiteLLM 多年供應商錯誤處理」）。
- 新：實作實際只用 `litellm.acompletion()`（**library form**）；階段 5（spec 012）為支援多 provider
  **再度確認採 library form**（不啟用 Proxy server）。

## 為什麼變
research 把選項寫得完整、有理由、有 alternatives，仍不足以防止「決策文件說 A、實作跑成 B」的漂移——
此漂移直到 Phase 3b 收尾使用者才點破（多花工又揹依賴沒享好處）。事後定形：litellm library form 的 CVE
集中度遠低於 Proxy form、涵蓋 100+ provider 不必逐家寫 adapter，且 Proxy form 的 virtual keys 與我們的
「分配」領域抽象不同軸（build-vs-adopt 以領域第一公民同不同軸判）。「攔截在前、領域自持」的判斷始終對；
錯的是沒在 specify 前把「用哪個形態」定死並守住。

## 狀態
✅ 已採用（library-only）。Proxy Server 形態 ⚰️ 否決，見 `tombstones.md`「整包改用 LiteLLM Proxy」。

## 註
Phase 011 曾一度 drop litellm 改 `AsyncAzureOpenAI` 直呼、Phase 5 又回 litellm——形態選對後採用/自製可進退。
在 arc 1 視角此漂移是**未察覺的隱性技術債**（spec/plan 均以「用 LiteLLM」陳述、未反省其實是自幹並行版）。
