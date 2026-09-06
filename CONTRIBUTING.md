# Contributing to MOD

Updated: 2026-09-02
Status: Current
Scope: Humans and all coding agents working in `/home/ubuntu/mod`

This repository is maintained on the primary run host, which also serves production from the same machine. There is no separate deployment host.

## Start here

Read these documents in order before making changes:

1. `AGENTS.md` — mandatory repository-wide rules.
2. `ENFORCEMENT.md` — how those rules are enforced at the point of action (gates, not just guidance).
3. `docs/CURRENT-STATE.md` — current runtime, data, and safety facts.
4. `PROJECT-LAYOUT.md` — directory and host boundaries.
5. The standard matching your task type — see the "Required reading by task type" table in `AGENTS.md`
   (e.g. frontend changes require `FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md`, DB/data require
   `DATA-AND-SECURITY-STANDARD.md`, any change requires `TESTING-STANDARD.md`). Read the matching one, not all.

If documents disagree, follow the authority order in `AGENTS.md`. The old collaboration state machine is archived
under `archive/legacy-collaboration/` and must not be used as an active workflow.

## Standard workflow

1. Run `git status --short` and inspect relevant existing changes.
2. Check for a more specific `AGENTS.md`, then read the source, tests, and current documentation for the area.
3. State the intended scope and identify any operation needing explicit authorization.
4. Make the smallest coherent change in the correct domain directory.
5. Add or update tests for changed behavior and regressions.
6. Run targeted checks, then run `make check` from the repository root.
7. Review `git diff --check`, `git diff`, and `git status --short`.
8. Update current documentation whenever facts, behavior, paths, commands, data, or deployment change.
9. Create a signed local commit with one intent and an English message of no more than seven words.
10. Report the validation result, remaining risks, deployment state, and commit ID.

## Change boundaries

Read-only inspection within the project is the default. Explicit authorization is required before database writes,
production service control, Nginx changes, cloud resource changes, destructive cleanup, or publishing anything
outside this local repository. Never modify `/home/ubuntu/modo` or another project.

## Commit contract

- Use `git commit -S` and the existing signing configuration.
- Use a lowercase English Conventional Commit type and no more than seven words in the subject.
- Keep one coherent intent per commit.
- Do not rewrite existing commits without explicit instruction.
- Do not add remotes, push, publish releases, or create a GitHub repository without explicit instruction.
- Never commit secrets, local data, generated CSV files, build output, dependency caches, or CLI logs.

## Standards

- `docs/development/PROJECT-ORGANIZATION.md`
- `docs/development/DEVELOPMENT-STANDARD.md`
- `docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md`
- `docs/development/COLLABORATION-STANDARD.md`
- `docs/development/TESTING-STANDARD.md`
- `docs/development/DOCUMENTATION-STANDARD.md`
- `docs/development/DATA-AND-SECURITY-STANDARD.md`
- `docs/development/SECRET-SCAN-HOOK-DESIGN.md`
- `docs/development/CLI-SCRIPT-POLICY.md`
- `docs/operations/USA-DEPLOYMENT-LAYOUT.md`
