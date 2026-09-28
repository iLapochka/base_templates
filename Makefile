COMPOSE_DIR = docker
COMPOSE     = docker compose -f $(COMPOSE_DIR)/docker-compose.yml

# ── Docker ────────────────────────────────────────────────────────────────────

# Full stack: API + PostgreSQL (runs alembic on start).
.PHONY: docker
docker:
	$(COMPOSE) up -d --build

.PHONY: docker-down
docker-down:
	$(COMPOSE) down

.PHONY: docker-logs
docker-logs:
	$(COMPOSE) logs -f

# PostgreSQL only — for running the app on the host during local development.
.PHONY: postgresql
postgresql:
	$(COMPOSE) up -d db

.PHONY: postgresql-down
postgresql-down:
	$(COMPOSE) stop db

# ── FastAPI ───────────────────────────────────────────────────────────────────

.PHONY: run
run:
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 9000

# ffmpeg is a system binary, not a Python package: install it once per machine.
.PHONY: ffmpeg
ffmpeg:
	brew install ffmpeg

# ── Alembic ───────────────────────────────────────────────────────────────────

.PHONY: migrate
migrate:
	uv run alembic upgrade head

.PHONY: migrations
migrations:
	uv run alembic revision --autogenerate -m "$(MSG)"

.PHONY: migrate-down
migrate-down:
	uv run alembic downgrade -1

# Throw the local database and every migration away, then generate one from the models as they
# stand. The migrations are tracked, so `git checkout core/alembic/versions/` brings them back.
.PHONY: from-scratch
from-scratch:
	rm -f local.db
	rm -rf core/alembic/versions/__pycache__
	find core/alembic/versions -name '*.py' -delete
	$(MAKE) migrations MSG="create schema"
	$(MAKE) migrate

# ── Code quality ──────────────────────────────────────────────────────────────

.PHONY: ruff
ruff:
	uv run ruff check . --fix --config=code_quality/.ruff.toml
	uv run ruff format . --config=code_quality/.ruff.toml

# What CI runs; `make ruff` has already formatted, so `check` does not repeat it.
.PHONY: format-check
format-check:
	uv run ruff format --check --config=code_quality/.ruff.toml src/

.PHONY: ty
ty:
	uv run mypy --config-file=code_quality/mypy.ini src/

.PHONY: lint
lint:
	uv run pylint --rcfile=code_quality/pylint.toml src/

.PHONY: layers
layers:
	uv run python scripts/check_ddd_layering.py

.PHONY: specs
specs:
	uv run python scripts/check_specs.py

.PHONY: tests
tests:
	uv run pytest tests/

.PHONY: hooks
hooks:
	uv run pre-commit run --all-files

.PHONY: check
check: hooks ruff ty lint layers specs tests
