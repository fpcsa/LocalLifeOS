PYTHON ?= python3
API_PYTHON := apps/api/.venv/bin/python

.PHONY: start stop install-api install-web migrate test-api lint-api typecheck-api test-web lint-web typecheck-web build-web check

start:
	docker compose up --build

stop:
	docker compose down

install-api:
	$(PYTHON) -m venv apps/api/.venv
	$(API_PYTHON) -m pip install -r apps/api/requirements-dev.txt

install-web:
	npm install

migrate:
	cd apps/api && .venv/bin/python -m alembic upgrade head

test-api:
	cd apps/api && .venv/bin/python -m pytest

lint-api:
	cd apps/api && .venv/bin/python -m ruff check .

typecheck-api:
	cd apps/api && .venv/bin/python -m mypy app

test-web:
	npm run test:web

lint-web:
	npm run lint:web

typecheck-web:
	npm run typecheck:web

build-web:
	npm run build:web

check: test-api lint-api typecheck-api test-web lint-web typecheck-web build-web
