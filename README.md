# start_templates — `fast-api-events`

Example **FastAPI events** template: a DDD backend skeleton where bounded contexts talk through an
in-process event bus, every long job runs in the background, and the rules are enforced by tooling
and by Claude Code hooks rather than by review alone.

```bash
git clone -b fast-api-events <repo-url> my-project
```

## Stack

- **FastAPI** + **uvicorn**, Python 3.13, **uv**
- **SQLAlchemy 2** (async) + **Alembic** — PostgreSQL in production, SQLite locally
- **sqladmin** — `/admin` for one operator, off unless a password and secret are set
- **ruff**, **mypy --strict**, **pylint**, **pytest** + **pytest-asyncio**, **pre-commit**
- **Docker** + compose (API + PostgreSQL)

## What's included

| Path | What it gives you |
| --- | --- |
| `src/shared/domain/` | `BaseEntity` (equal by id), `DomainEvent`, `EventBus` and `UnitOfWork` ports |
| `src/shared/infrastructure/` | `InProcessEventBus`, `SQLAlchemyUnitOfWork` (rolls back on failure), `BaseModel`, `SQLAlchemyRepository` |
| `src/shared/presentation/` | API-key dependency, session / unit-of-work deps, exception handlers, request-id middleware, `StrictSchema`, admin |
| `src/shared/call_logging.py` | `@log_call` — logs `Class.method(name=value)`; credentials hidden via `repr=False` |
| `core/` | pydantic-settings config (refuses a weak `API_KEY` outside local), async engine, Alembic |
| `code_quality/` | ruff, mypy, pylint configs |
| `scripts/` | `check_ddd_layering.py` (imports point inward, no processes in the core), `check_specs.py` |
| `specs/` | Behavioral specs indexed by `INDEX.md` — written before the code |
| `.claude/` | `CLAUDE.md` rules, hooks (no commit/push, no shell file edits, layering hints), spec skills |
| `.github/workflows/` | CI (one job per tool) and a Claude PR review hardened for `workflow_run` |

`CLAUDE.md` is written for a video-processing service (yt-dlp + ffmpeg) as the worked example —
rename the domain and keep the rules.

## Quick start

```bash
uv sync
cp .env.example .env
make migrate
make run          # http://localhost:9000, Swagger at /api/docs (local only)
make check        # pre-commit + ruff + mypy + pylint + layers + specs + pytest
```

### Start your own project from this template

```bash
git clone -b fast-api-events <repo-url> my-project
cd my-project
git remote remove origin
git remote add origin <your-repo-url>
git push -u origin main
```
