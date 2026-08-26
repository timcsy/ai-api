# 016：Dockerfile 從 `uv pip install .` 到 `uv export --frozen` + 依賴/碼分層
> 日期：2026-08-25

## 轉移
- 舊（superseded）：builder 用 `uv pip install .`（讀 pyproject range、把 `ai_api` 也裝進 site-packages），
  runtime 把整個 site-packages 當**單一 COPY 層**（隨碼變）。
- 新（rev 24）：`uv export --frozen --no-dev --no-emit-project` → `uv pip install --system -r`（依賴 pinned
  from uv.lock、排除專案本身）；專案碼改 runtime `COPY src/ ./src/` + `PYTHONPATH`。

## 為什麼變
距上次部署 17 天後 `helm upgrade` 一直 `pre-upgrade hooks failed`。根因鏈：`uv pip install .` 把 ai_api 烤進
site-packages、runtime 整層當單一 COPY → 改一行碼就換整層 digest（~1GB）→ 每次部署都重拉整包（學校上行慢
20+ 分）→ helm hook 等不到 image → hook timeout → 整個 upgrade 回滾（服務不受影響、舊 pod 續跑）。要穩定就得
**依賴層與專案碼分屬不同 layer**：依賴層輸入只剩 `pyproject.toml`+`uv.lock`，code-only 改動不動它、node 命中
既有層。診斷：慢拉 vs 壞拉——只有 `Pulling`、無 `Failed/Back-off` = 慢；治標＝ warmer Pod 預拉。

## 狀態
✅ 已採用（治本）。前置驗證：全走 `python3 -m`（alembic/uvicorn/create_admin）、無 `importlib.metadata` 自我
版本依賴，故專案不需被 pip 安裝。詳見 `concepts/依賴層與專案碼層要分屬不同容器層.md`。
