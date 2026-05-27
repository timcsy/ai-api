# ai-api Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-27

## Active Technologies
- Python 3.11+（同 Phase 1） (002-auth-membership)
- PostgreSQL（含新表：members、sessions、email_whitelist、 (002-auth-membership)
- Python 3.11+（不變） (003-hardening)
- PostgreSQL（不變）；無新表，只修 Allocation enum (003-hardening)
- PostgreSQL（生產）/ SQLite（dev、CI） (004-usage-billing)
- GitHub Actions workflow YAML（無 source code 變更） (005-supply-chain)
- PostgreSQL（生產）/ SQLite（dev、CI）— `model_catalog` 表用 JSON columns (007-model-catalog)
- TypeScript（strict） + Python 3.11+（既有，不變） (008-frontend-scaffold)
- 無（前端不直接接 DB） (008-frontend-scaffold)
- 同 3b.0（前端 TS 5.x / React 19 / Vite 6）+ Python 3.11+ 後端 (009-member-view)
- 無；後端不動 schema (009-member-view)
- 同 3b.1 (010-admin-suite)
- Python 3.11+（後端不變）+ TypeScript strict / React 19 / Vite 6（前端不變） + FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、`litellm`（library only，預計 `>=1.55,<2`）、`cryptography`（Fernet）、既有前端 stack（shadcn/ui + TanStack Query） (012-multi-provider-access)
- PostgreSQL（生產）/ SQLite（dev、CI）；新表 `provider_credentials`、`member_tags`；既有 `model_catalog` 加欄 (012-multi-provider-access)
- Python 3.11+ + FastAPI、SQLAlchemy 2.x async、Pydantic v2（既有，不新增套件） (017-admin-bootstrap)
- PostgreSQL（生產）/ SQLite（dev、CI）；本功能不新增表、不新增 migration (017-admin-bootstrap)

- Python 3.11+ + LiteLLM（proxy core）、FastAPI（admin API）、 (001-gateway-core)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 017-admin-bootstrap: Added Python 3.11+ + FastAPI、SQLAlchemy 2.x async、Pydantic v2（既有，不新增套件）
- 012-multi-provider-access: Added Python 3.11+（後端不變）+ TypeScript strict / React 19 / Vite 6（前端不變） + FastAPI、SQLAlchemy 2.x async、Alembic、Pydantic v2、`litellm`（library only，預計 `>=1.55,<2`）、`cryptography`（Fernet）、既有前端 stack（shadcn/ui + TanStack Query）
- 010-admin-suite: Added 同 3b.1


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
