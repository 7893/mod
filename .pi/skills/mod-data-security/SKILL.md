---
name: mod-data-security
description: Database operation safety, credential security, read-only verification first, and migration boundaries.
---
> **Authoritative Standard**: This skill is a condensed execution reference. For full data security rules, see [DATA-AND-SECURITY-STANDARD.md](../../../docs/development/DATA-AND-SECURITY-STANDARD.md).


# MOD Data & Security Standard Skill

## 1. 只读检查先行 (Read-only Verification First)
- Before writing any script that deletes or modifies database data, ALWAYS run a read-only query (or dry-run) to inspect row counts, foreign key dependencies, and potential cross-boundary effects.
- Verify production credentials are kept in `.env.systemd` or environment files, NEVER hardcoded in git tracked code.

## 2. 生产库数据安全原则 (Production DB Safety)
- Database deletion must follow dependency hierarchy from child/leaf tables to parent tables:
  1. `integration_result`
  2. `document_voucher_link`
  3. `accounting_voucher_line`
  4. `accounting_voucher`
  5. `business_document_line`
  6. `business_document`
  7. `daily_stats` / `rollout_status_snapshot`
- Always verify financial cross-check integrity:
  - Debit equals Credit (`SUM(debit) == SUM(credit)`)
  - No orphan vouchers or links.
- Single transaction ownership: use `engine.begin()` context manager or transaction rollback on failure.

## 3. 凭据防泄漏 (Secret Scanning)
- Do not commit `.env`, passwords, or tokens into Git.
- CI and local pre-commit hook runs `python3 scripts/project/scan_secrets.py`.
