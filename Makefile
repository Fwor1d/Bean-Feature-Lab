.PHONY: setup web api worker test lint format typecheck build migrate presentation presentation-quick presentation-status presentation-stop

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e '.[dev]'
	cd apps/web && npm install
	.venv/bin/alembic upgrade head

web:
	cd apps/web && npm run dev

api:
	.venv/bin/uvicorn beanfeature_api.main:app --reload --host 127.0.0.1 --port 8000

worker:
	.venv/bin/beanfeature-worker

test:
	.venv/bin/pytest
	cd apps/web && npm test

lint:
	.venv/bin/ruff check .
	cd apps/web && npm run lint

format:
	.venv/bin/ruff format .

typecheck:
	cd apps/web && npm run typecheck

build:
	cd apps/web && npm run build

migrate:
	.venv/bin/alembic upgrade head

.PHONY: presentation presentation-quick

presentation:
	./scripts/presentation-named.sh

presentation-quick:
	./scripts/presentation.sh

presentation-status:
	.venv/bin/python scripts/presentation.py status

presentation-stop:
	.venv/bin/python scripts/presentation.py stop
