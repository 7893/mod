# MOD agent entrypoint

Follow explicit user instructions first. This compact entry supersedes the previous eager-reading policy;
the complete previous entries are preserved in docs/history/2026-09-11-HARNESS-ENTRYPOINTS.md.
Do not load that historical snapshot at task startup.

## Always
- Inspect git status and relevant diffs. Preserve existing work and all historical content.
- Work within the requested scope. Database writes, service/cloud changes and production publishing require explicit authority.
- Credentials stay in approved environment mechanisms; never print or commit secrets.
- Source workspace and production share a host. Local builds are isolated; publish.sh changes production and needs authorization.
- Do not modify frozen artifacts or other projects unless the user explicitly places them in scope.
- Temporary scripts belong in your CLI's scripts/<owner>/ directory; stable shared scripts in scripts/project/ need documentation.
- Preserve tracked docs. Superseded text stays marked or archived intact; never silently discard it.
- Use one canonical implementation, no iteration suffixes or catch-all modules. Aim for <=400 source lines;
  >600 requires splitting or documented reasons. No historical multi-agent state machine.
- Use signed local commits with lowercase Conventional Commit type and <=7-word English subject.
  Do not push, publish, amend or rewrite history without authorization.
- Truth order: explicit instructions / AGENTS; relevant CURRENT-STATE facts; source/tests/config; living standards; history.

## Load only what the task needs
Start with the current task, these rules, and the CURRENT-STATE "操作边界" section.
Get a domain index with:
    node /home/ubuntu/local-harness/cli.mjs context --scope frontend
Scopes: frontend, backend, data, docs, tooling. Pi also exposes local_harness and /harness.
For a mapped KI, prefer task --target KI-076 --intent investigate: target references/checks stay independent of unrelated diffs.
Investigation is plan-only; repair/accept checks require explicit execution. Automated checks never close a KI.
Read the relevant exact sections, then related source/tests. Add other domains only when dependencies require it.
Do not preload all docs, all CURRENT-STATE, all skills, or previous KI records.
The manifest .pi/harness.json is a navigation/check map, not a second copy of standards.
If the local harness is unavailable, inspect that manifest and read the same references directly.
Use full standards when the task spans the whole standard or section boundaries are insufficient.

## Action-specific requirements
- Frontend: skeleton/component/token contracts; existing shared blocks; behavior tests and visual checks for layout changes.
- Backend/API: development and API compatibility sections; database/security rules if access is needed.
- Documents: documentation standard/lifecycle sections relevant to editing, KI or history.
- KI is for defects only; new capabilities use feature/task tracking. Keep board/detail status aligned.
- Changed behavior/facts must update relevant living docs and CURRENT-STATE content, not merely its date.
- Database investigation: use scripts/project/safe_db_query.py or the project mod_db_query tool.
- Production: read ENFORCEMENT gates B/D and deployment standards; check make sim-status before authorized publishing.
- New scripts: read docs/development/CLI-SCRIPT-POLICY.md before creating them.
- Detailed enforcement: ENFORCEMENT.md; contribution workflow: CONTRIBUTING.md. Read applicable sections at action time.

## Verify
Run targeted pre-flight before full acceptance. Public harness returns summaries and local log paths;
a scoped pass is not full acceptance. Read failing details without reinjecting complete passing logs.
Full make check remains required before each commit. Do not weaken gates or reuse stale results.
Report changes, validation, unfinished work, deployment status and commit ID.
Local harness setup/rollback: docs/development/LOCAL-HARNESS.md.
