.PHONY: check backend-check frontend-check doc-check pre-flight sim-status

pre-flight:
	@./scripts/project/pre_flight.sh

sim-status:
	@python3 scripts/project/check_simulator_status.py

check: backend-check frontend-check doc-check

backend-check:
	cd backend && uv run ruff check app tests ../simulation
	cd backend && uv run python -m pytest -p no:cacheprovider -q

frontend-check:
	cd frontend && pnpm run lint
	cd frontend && pnpm run lint:styles
	python3 scripts/project/lint_frontend_arbitrary_values.py
	python3 scripts/project/lint_frontend_styles.py
	cd frontend && pnpm test
	cd frontend && pnpm run typecheck
	cd frontend && pnpm run build

doc-check:
	python3 scripts/project/check_public_sanitization.py
	python3 scripts/project/sanitize_history.py --check
	python3 scripts/project/check_history_integrity.py
	python3 scripts/project/check_semantic_contracts.py
	# Linked-worktree hooks export Git paths; lychee inspects its own cached repository.
	env -u GIT_DIR -u GIT_WORK_TREE -u GIT_COMMON_DIR uv run --project backend pre-commit run lychee --all-files
	python3 scripts/project/check_document_governance.py
	python3 scripts/project/check_doc_sync.py
	python3 scripts/project/check_changelog.py
	python3 -m unittest discover -s scripts/project/tests -p 'test_*.py'
