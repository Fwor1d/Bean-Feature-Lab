.PHONY: setup install install-python web api worker test lint format typecheck build migrate presentation presentation-quick presentation-status presentation-stop

PYTHON ?= python3.11

setup: install migrate

# Install dependencies without creating or migrating scientific runtime state.
install: install-python
	cd apps/web && npm ci

install-python:
	$(PYTHON) -c 'import sys; assert sys.version_info[:2] == (3, 11), "BeanFeature Lab requires Python 3.11"'
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -r requirements/bootstrap.lock
	.venv/bin/python -m pip install -r requirements/python311.lock
	.venv/bin/python -m pip install --no-build-isolation --no-deps -e '.[dev]'
	.venv/bin/python -m pip check

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
