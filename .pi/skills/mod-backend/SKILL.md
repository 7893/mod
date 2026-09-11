---
name: mod-backend
description: Backend service architecture, FastAPI routing boundaries, simulation engine, and API standards.
---
> **Authoritative Standard**: This skill is a condensed execution reference. For full architectural rules, see [DEVELOPMENT-STANDARD.md](../../../docs/development/DEVELOPMENT-STANDARD.md).


# MOD Backend Development Skill

When working on `backend/` or `simulation/`, adhere to the following architectural rules:

## 1. 架构边界 (Boundaries)
- `backend/app/api*.py`: Pure routing, query parameter validation, and HTTP response orchestration. **DO NOT** write complex SQL query builders or domain business logic directly in API routes.
- `backend/app/services/`: Application use cases, snapshot generation, cross-data source orchestration.
- `simulation/`: Business simulation engine and generators (`expense_playbook.py`, `runtime_service.py`).

## 2. 时间与数据生成规则 (Temporal Constraints)
- **Zero Future Dates**: Generated documents (`business_document.submit_time`, `accounting_voucher.gen_time`, etc.) MUST NEVER be in the future (`> NOW()`).
- Time sequence must remain strictly monotonically increasing: `submit_time < approve_time < gen_time < integration_time <= now`.
- Always respect China Standard Time (HKT / CST, UTC+8).

## 3. 模拟器常驻循环与限流 (Simulator Safeguards)
- Simulator uses a rate limiter (20/min hard cap, 5000/day).
- Never allow unhandled exceptions in the simulation cycle; gracefully report status in `/api/simulator/status`.
- Sub-modules must not independently commit connection transactions (`auto_commit=False`), transactions are owned by the root orchestrator.

## 4. 验证要求
- Run `backend/.venv/bin/ruff check app tests ../simulation`
- Run `backend/.venv/bin/python -m pytest -p no:cacheprovider -q`
