---
name: mod-data-security
description: Index for database operation safety, credential security, and read-only verification.
---
> **Authoritative Standard**: This skill is a condensed navigation index. For full data security rules, see [DATA-AND-SECURITY-STANDARD.md](../../../docs/development/DATA-AND-SECURITY-STANDARD.md).

# MOD Data & Security Index

This skill serves as a navigation index. **Do not guess rules; read the referenced documents on-demand.**

## What to Read When...

- **Querying the database**: Read `docs/development/DATA-AND-SECURITY-STANDARD.md`. You MUST use `mod_db_query` or `scripts/project/safe_db_query.py`.
- **Modifying or deleting data**: Read `docs/development/DATA-AND-SECURITY-STANDARD.md` (Section: Production DB Safety). Deletions must follow the foreign-key hierarchy.
- **Handling credentials**: Read `docs/development/DATA-AND-SECURITY-STANDARD.md`. Never hardcode secrets; use `.env.systemd`.

## Validation
Always run read-only queries before any destructive actions. Secrets are checked automatically via `make check`.
