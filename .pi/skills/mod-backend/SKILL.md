---
name: mod-backend
description: Index for backend service architecture, simulation engine, and API standards.
---
> **Authoritative Standard**: This skill is a condensed navigation index. For full architectural rules, see [DEVELOPMENT-STANDARD.md](../../../docs/development/DEVELOPMENT-STANDARD.md).

# MOD Backend Development Index

This skill serves as a navigation index. **Do not guess rules; read the referenced documents on-demand.**

## What to Read When...

- **Creating or editing an API route**: Read `docs/development/DEVELOPMENT-STANDARD.md` (Section: Boundaries). Routes go in `backend/app/api*.py`.
- **Writing business logic**: Read `docs/development/DEVELOPMENT-STANDARD.md`. Logic goes in `backend/app/services/`.
- **Handling dates and time**: Read `docs/development/DEVELOPMENT-STANDARD.md` (Section: Temporal Constraints). Time must be UTC+8 and never in the future.
- **Interacting with Simulator**: Read `docs/development/DEVELOPMENT-STANDARD.md` and check status via `make sim-status`.

## Validation
Run pre-flight checks before committing: `make pre-flight` (or `pi /pre-flight`).
