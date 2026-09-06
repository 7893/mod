# MOD repository rules

These rules apply to the entire repository.

## Source of truth

- Before changing the project, read `ENFORCEMENT.md`, `docs/CURRENT-STATE.md`, `CONTRIBUTING.md`, and the relevant
  standard under `docs/development/`.
- `ENFORCEMENT.md` defines how these rules are enforced at the point of action. Rules here describe what to do;
  `ENFORCEMENT.md` describes the gates that stop violations. Read both.
- When information conflicts, use this order: `AGENTS.md` and explicit user instructions; `docs/CURRENT-STATE.md`;
  maintained source, tests, and deployment configuration; current standards; historical documentation.
- The old multi-agent collaboration state machine (dispatcher, agents, and its docs) is archived under
  `archive/legacy-collaboration/`. Do not run, restore, or maintain it.
- The production site is rooted at the configured public domain (see deploy config); do not assume a `/mod/` deployment prefix.

## Required workflow

- Inspect `git status` and relevant diffs before editing. Preserve unrelated or pre-existing changes.
- Before acting, state the intent: what will change, the blast radius, whether it touches the database, production,
  or credentials, and the rollback path. Record facts back to current documentation after the change.
- Keep each task within its stated scope. Database writes, production changes, deletion, and cloud changes require
  explicit authorization and read-only target verification first.
- Add or update tests for behavior changes and regression fixes. Run targeted checks while working and `make check`
  before every commit, including documentation-only commits.
- Review `git diff --check`, `git diff`, and `git status` before committing. Update current documentation when behavior,
  architecture, paths, commands, data state, or deployment state changes.
- Finish with a concise handoff covering changes, validation, remaining risks, deployment state, and commit ID.

## Required reading by task type

Before touching an area, read the matching standard under `docs/development/`. This is mandatory — do not rely on
being told each time. Every task also reads this `AGENTS.md` first.

| If you change... | You MUST read first |
|---|---|
| Frontend (Vue/CSS/views/components) | `docs/development/FRONTEND-ARCHITECTURE-AND-CONSTRAINTS.md` (skeleton/component/Token three-layer contract; no ad-hoc CSS or arbitrary values) |
| Backend / services / API | `docs/development/DEVELOPMENT-STANDARD.md` |
| Database / data / credentials / migrations | `docs/development/DATA-AND-SECURITY-STANDARD.md` |
| Docs / decisions / issues | `docs/development/DOCUMENTATION-STANDARD.md` + `docs/development/DOCUMENTATION-LIFECYCLE.md` |
| CLI / one-off scripts | `docs/development/CLI-SCRIPT-POLICY.md` |
| Any change (always) | `docs/development/TESTING-STANDARD.md`; run `make check` before every commit |

Enforcement of these standards is described in `ENFORCEMENT.md`. Where CI gates exist (e.g. frontend arbitrary-value
lint, credential scan, commit-message check), a violation fails the build — read the standard, do not fight the gate.

## Script ownership

- Codex/OpenAI GPT scripts: `scripts/codex/`
- Claude Code scripts: `scripts/claude/`
- Kiro CLI scripts: `scripts/kiro/`
- Antigravity/agy scripts: `scripts/agy/`
- GitHub Copilot scripts: `scripts/copilot/`
- Human-authored temporary scripts: `scripts/user/`
- Reviewed, reusable project scripts: `scripts/project/`

Never create loose scripts in the repository root. An agent must not write into another agent's directory.
Generated outputs belong in that owner's ignored `tmp/` or `output/` directory. Stable project tooling may move
to `scripts/project/` only after it is documented and reviewed. Existing domain packages under `database/`
and `tools/` are grandfathered; do not add unrelated one-off scripts there. `database/` now holds only the
read-only acceptance verifier; the legacy batch generator/importer packages (formerly `generator/`) have been
retired to the ignored `archive/legacy-db-scripts/` — data is now produced by the simulation engine, not batch scripts.

## Project organization

- Group first-party code by domain and responsibility; never create catch-all `misc`, `utils`, or loose root modules.
- Single canonical version. This project has one evolving line, not coexisting versions. **Never append version or
  mode suffixes (`_v2`, `_v3`, `-v2`, `V2`, `_s`, etc.) to first-party modules, files, classes, database names, table
  names, or API routes to represent an "iteration".** Evolve the existing entity in place; iteration history lives in
  git, not in names. To preserve an old version for rollback, move it to `archive/` with a note — do not keep parallel
  `_v2`/`_v3` variants on the mainline. Names express responsibility, not a version number. (Exempt: external
  dependency versions, already-frozen data assets under `artifacts/`, ADR/KI record numbers, and ordered schema
  migration scripts — none of these are code-version suffixes.)
- Keep HTTP route modules thin. Put snapshot construction and business rules in `backend/app/services/`, external
  platform adapters in `backend/app/integrations/`, and simulation domain models in `backend/app/simulation/`.
- Keep compatibility shims only when an established import path must remain stable; new code imports the domain module.
- Organize first-party CSS under `frontend/src/styles/` by foundation, shared component, page, and responsive concern.
- Target no more than 400 lines for first-party source files. Files over 600 lines require splitting or a documented
  reason. Generated data, generated clients, vendored code, and third-party component bundles are exempt.
- Tests mirror the maintained domain they cover. Documentation belongs under `docs/development/`, `docs/operations/`,
  or another existing subject directory, never beside unrelated source.
- The primary run host `/home/ubuntu/mod` is the source-of-truth workspace and also serves production from the
  same machine. There is no separate deployment-only host.

## Documentation

- Current documentation must not copy unverified historical claims. Follow `docs/development/DOCUMENTATION-STANDARD.md`.
- `docs/CURRENT-STATE.md` records current facts only. Historical decisions and evidence must be clearly labeled and
  must not override current code, tests, or deployment configuration.
- New maintained documents need a title, updated date, status, scope, relative links, and no secrets or personal data.
- Never edit historical evidence to make it appear current. Add a current correction or an explicit historical notice.

## Safety

- Never commit `.env` files, credentials, private keys, wallets, database dumps, generated CSV data, or CLI logs.
- Do not modify frozen data under `artifacts/v2-sim-data/`.
- Production runs on the same host as the workspace. Building the frontend and reloading services affects
  production directly; treat frontend builds, service control, and Nginx changes as production changes.
- Database writes, backend/service control, Nginx changes, and cloud resource changes still require explicit scope.
- Do not modify or remove files belonging to `/home/ubuntu/modo` or other projects.

## Git

- Commit subjects must use a lowercase English Conventional Commit type (`feat`, `fix`, `docs`, `chore`,
  `refactor`, `test`, `build`, `ci`, `perf`, `style`, or `revert`) and contain no more than seven words.
- Every commit must be signed with the existing local signing configuration: `git commit -S`.
- Keep one coherent intent per commit. Do not amend, rebase, reset, squash, or rewrite existing commits unless the user
  explicitly requests it.
- Do not add a remote, push, publish, or create a GitHub repository unless the user explicitly requests it.
- Keep generated assets and local-only data out of Git via `.gitignore`.

## Verification

- Run `make check` before committing maintained code.
- Keep the working tree clean and report any intentionally untracked files.
