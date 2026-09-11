---
name: mod-frontend
description: Index for frontend guidelines, layout contracts, and design tokens.
---
> **Authoritative Standard**: This skill is a condensed navigation index. For full frontend rules, see [FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md](../../../docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md).

# MOD Frontend Development Index

This skill serves as a navigation index. **Do not guess rules; read the referenced documents on-demand.**

## What to Read When...

- **Building a new screen/layout**: Read `docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` (Section: Layout Contract). Use Tailwind grid templates.
- **Creating panels or tables**: Read `docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` (Section: Component Contract). Use `CockpitPanel.vue` and `components/ledger/`.
- **Styling elements**: Read `docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` (Section: Token Contract). **Arbitrary Tailwind values are strictly forbidden.** Use `theme.css` tokens.

## Validation
Run pre-flight checks before committing: `make pre-flight` (or `pi /pre-flight`).
