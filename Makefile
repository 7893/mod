.PHONY: check backend-check frontend-check

check: backend-check frontend-check

backend-check:
	cd backend && .venv/bin/ruff check app tests
	cd backend && .venv/bin/python -m pytest -p no:cacheprovider -q

frontend-check:
	python3 scripts/project/lint_frontend_arbitrary_values.py
	cd frontend && pnpm run typecheck
	cd frontend && pnpm run build
