# ai-api Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-05-23

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
- 008-frontend-scaffold: Added TypeScript（strict） + Python 3.11+（既有，不變）
- 007-model-catalog: Added Python 3.11+
- 006-quota-pool: Added Python 3.11+


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
